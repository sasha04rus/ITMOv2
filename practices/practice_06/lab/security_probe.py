"""HTTP-only regressions against a fresh, owned, loopback Mini Shop process."""
import argparse
import html
import json
from pathlib import Path
import queue
import signal
import subprocess
import sys
import threading
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

LAB = Path(__file__).resolve().parent
PROJECT = LAB.parent
XSS = '<script>window.__miniShopXss = 1</script>'


class LocalShop:
    def __enter__(self):
        self.process = subprocess.Popen(
            [sys.executable, '-u', str(LAB / 'service.py'), '--port', '0'],
            cwd=LAB, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        )
        lines = queue.Queue()
        def read_startup():
            for _ in range(2):
                lines.put(self.process.stdout.readline().strip())
        threading.Thread(target=read_startup, daemon=True).start()
        try:
            first, second = lines.get(timeout=12), lines.get(timeout=12)
            self.base = first.split('Local exercise: ', 1)[1]
            target = urlsplit(self.base)
            if target.scheme != 'http' or target.hostname != '127.0.0.1' or not target.port:
                raise RuntimeError('Refusing a non-loopback exercise target')
            self.root = Path(second.split('Disposable fixture files: ', 1)[1]).resolve()
            if not self.root.name.startswith('itmo-practice-06-'):
                raise RuntimeError('Unexpected fixture root from owned subprocess')
            self.tokens = {}
            return self
        except Exception:
            self.__exit__(None, None, None)
            raise

    def __exit__(self, *_):
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGINT)
            try:
                self.process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.process.stdout.close()
        self.process.stderr.close()

    def call(self, method, path, body=None, user=None, headers=None, raw=None):
        if not path.startswith('/') or path.startswith('//'):
            raise ValueError('Only relative paths on the owned exercise server are allowed')
        actual_headers = {'Content-Type': 'application/json'}
        if user:
            actual_headers['X-Token'] = self.tokens[user]
        actual_headers.update(headers or {})
        data = raw if raw is not None else json.dumps(body).encode() if body is not None else None
        request = Request(self.base + path, data=data, headers=actual_headers, method=method)
        try:
            response = urlopen(request, timeout=8)
        except HTTPError as error:
            response = error
        with response:
            text = response.read().decode('utf-8', errors='replace')
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                payload = text
            return response.status, payload

    def login(self, user='alice'):
        status, data = self.call('POST', '/login', {'username': user, 'password': 'learn-' + user})
        if status != 200:
            raise RuntimeError('Login failed for synthetic account: ' + user)
        self.tokens[user] = data['token']
        return data['token']

    def files(self):
        if not self.root.exists():
            return []
        return sorted(str(path.relative_to(self.root)) for path in self.root.rglob('*') if path.is_file())


def run(phase):
    results = []
    with LocalShop() as shop:
        for user in ['alice', 'bob', 'staff']:
            shop.login(user)

        def probe(case_id, name, method, path, expected, predicate, body=None,
                  user=None, headers=None, raw=None):
            status, response = shop.call(method, path, body, user, headers, raw)
            secure = bool(predicate(status, response))
            results.append({
                'id': case_id, 'name': name, 'request': {'method': method, 'path': path,
                'body': body if raw is None else raw.decode(errors='replace'),
                'actor': user or 'anonymous', 'extra_headers': headers or {}},
                'status': status, 'response': response, 'secure_expected': expected,
                'secure': secure,
            })
            return status, response

        probe('S01', 'anonymous profile', 'GET', '/profile?id=1', '401', lambda s, r: s == 401)
        probe('S02', 'foreign profile IDOR', 'GET', '/profile?id=2', '403; no Bob data',
              lambda s, r: s == 403 and 'TEST_BOB' not in json.dumps(r), user='alice')
        probe('S03', 'profile SQL injection', 'GET', '/profile?' + urlencode({'id': '1 OR 1=1'}),
              '400', lambda s, r: s == 400, user='alice')
        probe('S04', 'search SQL injection', 'GET', '/search?' + urlencode({'q': "' OR 1=1--"}),
              'literal search or 400; no Bob data',
              lambda s, r: s in (200, 400) and 'TEST_BOB' not in json.dumps(r), user='alice')
        probe('S05', 'anonymous orders', 'GET', '/orders', '401', lambda s, r: s == 401)
        probe('S06', 'orders owner isolation', 'GET', '/orders', '200; all orders owned by Alice',
              lambda s, r: s == 200 and isinstance(r, list) and all(x['owner'] == 1 for x in r), user='alice')
        probe('S07', 'spoofed staff header', 'GET', '/admin/export', '403',
              lambda s, r: s == 403, user='alice', headers={'X-Role': 'staff'})
        probe('S08', 'anonymous staff spoof', 'GET', '/admin/export', '401',
              lambda s, r: s == 401, headers={'X-Role': 'staff'})
        probe('S09', 'price tampering', 'POST', '/orders', 'reject or use catalog price 5000',
              lambda s, r: s == 400 or s == 201 and r.get('price') == 5000,
              body={'product': 'chair', 'price': -1}, user='alice')
        probe('S10', 'foreign receipt', 'GET', '/files?user=bob&path=receipt.txt', '403',
              lambda s, r: s == 403, user='alice')
        probe('S11', 'private file traversal inside fixture', 'GET',
              '/files?' + urlencode({'user': 'alice', 'path': '../../private/operator-note.txt'}),
              '403; no operator secret', lambda s, r: s == 403 and 'TEST_ONLY_OPERATOR_SECRET' not in json.dumps(r), user='alice')
        probe('S12', 'foreign assistant order', 'GET', '/assistant/context?order_id=2', '403',
              lambda s, r: s == 403, user='alice')
        probe('S13', 'assistant context SQL injection', 'GET',
              '/assistant/context?' + urlencode({'order_id': '1 OR 1=1'}), '400',
              lambda s, r: s == 400, user='alice')
        probe('S14', 'anonymous assistant file', 'POST', '/assistant/execute', '401',
              lambda s, r: s == 401,
              body={'decision': {'tool': 'read_file', 'arguments': {'path': 'files/alice/receipt.txt'}}})
        probe('S15', 'assistant private file', 'POST', '/assistant/execute', '403',
              lambda s, r: s == 403,
              body={'decision': {'tool': 'read_file', 'arguments': {'path': 'private/operator-note.txt'}}}, user='alice')
        probe('S16', 'assistant profile export', 'POST', '/assistant/execute', '403',
              lambda s, r: s == 403,
              body={'decision': {'tool': 'export_profiles', 'arguments': {}}}, user='alice')
        probe('S17', 'anonymous logs', 'GET', '/debug/logs', '401', lambda s, r: s == 401)
        probe('S18', 'customer logs', 'GET', '/debug/logs', '403', lambda s, r: s == 403, user='alice')
        probe('S19', 'stored active HTML', 'POST', '/reviews', '201', lambda s, r: s == 201,
              body={'product': 'chair', 'text': XSS}, user='alice')
        probe('S20', 'stored XSS rendering', 'GET', '/reviews/view', 'escaped script, no active script',
              lambda s, r: s == 200 and isinstance(r, str) and html.escape(XSS) in r and XSS not in r, user='alice')
        probe('S21', 'JSON array body', 'POST', '/login', '400; no internal exception',
              lambda s, r: s == 400 and 'type' not in r, raw=b'[]')
        probe('S22', 'malformed JSON', 'POST', '/login', '400', lambda s, r: s == 400, raw=b'{')
        probe('S23', 'missing product', 'POST', '/orders', '400', lambda s, r: s == 400, body={}, user='alice')
        probe('S24', 'malformed decision', 'POST', '/assistant/execute', '400', lambda s, r: s == 400,
              body={'decision': 'not an object'}, user='alice')
        secrets = ['learn-alice', 'learn-bob', 'learn-staff', *shop.tokens.values()]
        probe('S25', 'staff logs contain no credentials', 'GET', '/debug/logs',
              '200; no passwords or session tokens',
              lambda s, r: s == 200 and not any(secret in json.dumps(r) for secret in secrets), user='staff')
        probe('S26', 'missing receipt does not expose internal error', 'GET', '/files?user=alice&path=missing.txt',
              '403 or 404, not 500', lambda s, r: s in (403, 404) and 'type' not in r, user='alice')

        statuses = [shop.call('POST', '/reviews', {'product': 'chair', 'text': 'capacity check'}, 'alice')[0] for _ in range(129)]
        results.append({'id': 'S27', 'name': 'bounded review storage', 'secure_expected': '429 after finite capacity <=129',
                        'statuses': statuses, 'secure': 429 in statuses})
        statuses = [shop.call('POST', '/login', {'username': 'alice', 'password': 'learn-alice'})[0] for _ in range(260)]
        results.append({'id': 'S28', 'name': 'bounded sessions', 'secure_expected': '429 before 260 new sessions',
                        'statuses': statuses, 'secure': 429 in statuses})
        before_files = shop.files()
        status, response = probe('S29', 'forced fixture deletion', 'POST', '/assistant/execute',
              '403 and original files retained', lambda s, r: s == 403,
              body={'decision': {'tool': 'delete_tree', 'arguments': {'path': '.'}}}, user='alice')
        after_files = shop.files()
        results[-1].update({'files_before': before_files, 'files_after': after_files})
        results[-1]['secure'] = results[-1]['secure'] and after_files == before_files
        metadata = {'base': shop.base, 'owned_server_pid': shop.process.pid,
                    'fixture_root': str(shop.root), 'scope': 'Only owned loopback process and disposable fixture'}
    report = {'phase': phase, 'transport': 'real HTTP to subprocess', **metadata,
              'summary': {'checks': len(results), 'secure': sum(x['secure'] for x in results),
                          'unsafe': sum(not x['secure'] for x in results)}, 'results': results}
    folder = PROJECT / 'evidence' / phase
    folder.mkdir(parents=True, exist_ok=True)
    (folder / 'probes.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report['summary']))
    return 0 if phase == 'before' or all(x['secure'] for x in results) else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['before', 'after'], required=True)
    raise SystemExit(run(parser.parse_args().phase))
