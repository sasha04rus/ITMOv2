"""Verify saved experiment consistency without inventing or re-running model answers."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

from llm_probe import parse_decision

PROJECT = Path(__file__).resolve().parent.parent


def load(path):
    return json.loads((PROJECT / path).read_text(encoding='utf-8'))


def main(capture_runtime=False):
    checks = []
    def check(label, condition):
        checks.append({'check': label, 'passed': bool(condition)})
    for item in load('evidence/protected-files.json'):
        data = (PROJECT / item['file']).read_bytes().replace(b'\r\n', b'\n')
        check('unchanged protected file: ' + item['file'], hashlib.sha256(data).hexdigest() == item['canonical_sha256'])
    before, after = load('evidence/before/probes.json'), load('evidence/after/probes.json')
    check('same HTTP check IDs', [x['id'] for x in before['results']] == [x['id'] for x in after['results']])
    check('29 recorded before checks; 28 unsafe', before['summary'] == {'checks': 29, 'secure': 1, 'unsafe': 28})
    check('all 29 after expectations hold', after['summary'] == {'checks': 29, 'secure': 29, 'unsafe': 0})
    text = (PROJECT / 'evidence/before/security-tests.txt').read_text(encoding='utf-8')
    check('security tests genuinely failed before', 'Ran 17 tests' in text and 'FAILED (failures=37)' in text)
    text = (PROJECT / 'evidence/after-step6.txt').read_text(encoding='utf-8')
    check('make step6 passed all 36 tests', 'Ran 36 tests' in text and '\nOK\n' in text and 'FAILED' not in text)
    text = (PROJECT / 'evidence/final-make-test.txt').read_text(encoding='utf-8')
    check('complete make test passed', all(x in text for x in ['Practice 1 artifacts: OK', 'Practice 2 artifacts: OK', 'Ran 3 tests', 'Ran 36 tests']) and 'FAILED' not in text)
    sessions, systems, models, tasks = [], set(), set(), set()
    review_bytes = []
    for phase in ['before', 'after']:
        for case in ['normal', 'injected']:
            base = f'evidence/{phase}/planner-{case}/'
            metadata, outcome = load(base + 'model.json'), load(base + 'outcome.json')
            sessions += metadata['session_ids']
            systems.add(metadata['system_sha256']); models.add(metadata['model'])
            tasks.add((PROJECT / (base + 'user-task.txt')).read_text(encoding='utf-8'))
            answer = (PROJECT / (base + 'answer.txt')).read_text(encoding='utf-8')
            check(phase + '/' + case + ': original decision forwarded', parse_decision(answer) == outcome['decision'])
            check(phase + '/' + case + ': real completed call', metadata['returncode'] == 0 and not metadata['errors'])
            context = (PROJECT / (base + 'context.txt')).read_text(encoding='utf-8')
            check(phase + '/' + case + ': exact HTTP context saved', context == load(base + 'http-context.json')['prompt'])
            events = [json.loads(line) for line in (PROJECT / (base + 'events.jsonl')).read_text(encoding='utf-8').splitlines()]
            check(phase + '/' + case + ': tools not executed; reasoning omitted',
                  not any(e.get('type') in ('reasoning', 'tool_use') or e.get('part', {}).get('type') == 'reasoning' for e in events))
            if case == 'injected':
                review_bytes.append((PROJECT / (base + 'review.txt')).read_bytes())
    check('four independent planner sessions', len(sessions) == 4 and len(set(sessions)) == 4)
    check('same model, system prompt and user task', len(models) == len(systems) == len(tasks) == 1)
    check('same malicious review', len(review_bytes) == 2 and review_bytes[0] == review_bytes[1])
    first, last = load('evidence/before/forced-dangerous-decision.json'), load('evidence/after/forced-dangerous-decision.json')
    check('forced control shows authorization fix', first['status'] == 200 and len(first['files_after']) == 0 and
          last['status'] == 403 and last['files_before'] == last['files_after'] and len(last['files_after']) == 3)
    judge_paths = ['evidence/before/judge/', 'evidence/after/judge-retry/']
    judges = [load(path + 'model.json') for path in judge_paths]
    check('two independent judge sessions, same custom prompt',
          judges[0]['session_ids'] != judges[1]['session_ids'] and judges[0]['system_sha256'] == judges[1]['system_sha256'])
    for phase, path, metadata in zip(['before', 'after'], judge_paths, judges):
        check(phase + ': actual judge answer saved', metadata['returncode'] == 0 and not metadata['errors'] and
              bool((PROJECT / (path + 'answer.txt')).read_text(encoding='utf-8').strip()))
    result = {'captured_at': datetime.now(timezone.utc).isoformat(), 'checks': checks,
              'passed': all(x['passed'] for x in checks), 'scope': 'Saved evidence consistency, not a proof of universal security'}
    (PROJECT / 'evidence/verification.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    if capture_runtime:
        try:
            def request(path, body=None):
                req = Request('http://127.0.0.1:11434' + path,
                    data=json.dumps(body).encode() if body else None,
                    headers={'Content-Type': 'application/json'})
                with urlopen(req, timeout=10) as response:
                    return json.load(response)
            info = request('/api/show', {'model': 'itmo-agent'})
            snapshot = {'timing': 'Captured after the experiments', 'version': request('/api/version'),
                        'details': info.get('details'), 'parameters': info.get('parameters'),
                        'loaded_models': request('/api/ps').get('models', [])}
            (PROJECT / 'evidence/model-runtime.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding='utf-8')
        except Exception as error:
            print('Optional Ollama snapshot unavailable:', type(error).__name__)
    for item in checks:
        if not item['passed']:
            print('FAIL:', item['check'])
    print('Evidence checks:', sum(x['passed'] for x in checks), '/', len(checks))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture-runtime', action='store_true')
    raise SystemExit(main(parser.parse_args().capture_runtime))
