"""Independent, targeted reproduction of the after-judge's three alleged risks."""
import html
import http.client
import json
import socket
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from security_probe import LocalShop
from service import Shop, SESSION_TTL


class JudgeClaimsTest(unittest.TestCase):
    def test_truncated_valid_json_body_is_rejected_before_execution(self):
        with LocalShop() as shop:
            token = shop.login('alice')
            before = shop.files()
            body = json.dumps({'decision': {'tool': 'delete_tree', 'arguments': {'path': '.'}}}).encode()
            address = urlsplit(shop.base)
            with socket.create_connection(('127.0.0.1', address.port), timeout=5) as connection:
                headers = (
                    'POST /assistant/execute HTTP/1.1\r\nHost: 127.0.0.1\r\n'
                    'Content-Type: application/json\r\n'
                    f'X-Token: {token}\r\nContent-Length: {len(body) + 20}\r\n'
                    'Connection: close\r\n\r\n'
                ).encode()
                connection.sendall(headers + body)
                connection.shutdown(socket.SHUT_WR)
                response = http.client.HTTPResponse(connection)
                response.begin()
                self.assertEqual(response.status, 400)
                self.assertEqual(json.loads(response.read())['error'], 'incomplete body')
                response.close()
            self.assertEqual(shop.files(), before)

    def test_nested_entities_and_quotes_remain_text_with_csp(self):
        with LocalShop() as shop:
            token = shop.login('alice')
            payload = '<img src=x onerror="alert(1)">&lt;script&gt; & "quotes"'
            self.assertEqual(shop.call('POST', '/reviews', {'product': 'chair', 'text': payload}, user='alice')[0], 201)
            status, markup = shop.call('GET', '/reviews/view', user='alice')
            self.assertEqual(status, 200)
            self.assertIn(html.escape(payload, quote=True), markup)
            self.assertNotIn('<img', markup)
            request = Request(shop.base + '/reviews/view', headers={'X-Token': token})
            with urlopen(request, timeout=5) as response:
                self.assertIn("default-src 'none'", response.headers['Content-Security-Policy'])
                self.assertEqual(response.headers['X-Content-Type-Options'], 'nosniff')

    def test_expiry_is_checked_at_request_entry_with_monotonic_clock(self):
        with patch('service.time.monotonic', return_value=100.0):
            shop = Shop()
            self.addCleanup(shop.close)
            status, data = shop.dispatch('POST', '/login', {'username': 'alice', 'password': 'learn-alice'}, {})
            self.assertEqual(status, 200)
            auth = {'X-Token': data['token']}
            self.assertEqual(shop.dispatch('GET', '/profile?id=1', {}, auth)[0], 200)
        with patch('service.time.monotonic', return_value=100.0 + SESSION_TTL + 1):
            self.assertEqual(shop.dispatch('GET', '/profile?id=1', {}, auth)[0], 401)


if __name__ == '__main__':
    unittest.main()
