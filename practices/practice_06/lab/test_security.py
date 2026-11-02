"""Security assertions deliberately fail on the original course service."""
import html
import json
import unittest
from urllib.parse import urlencode
from security_probe import LocalShop, XSS


class SecurityTest(unittest.TestCase):
    def setUp(self):
        self.shop = LocalShop().__enter__()
        self.addCleanup(self.shop.__exit__, None, None, None)
        for user in ['alice', 'bob', 'staff']:
            self.shop.login(user)

    def call(self, method, path, body=None, user='alice', **kwargs):
        return self.shop.call(method, path, body=body, user=user, **kwargs)

    def test_anonymous_private_routes_require_session(self):
        for path in ['/profile?id=1', '/search?q=TEST', '/orders', '/files', '/debug/logs', '/assistant/context']:
            with self.subTest(path=path):
                self.assertEqual(self.call('GET', path, user=None)[0], 401)

    def test_profile_owner(self):
        self.assertEqual(self.call('GET', '/profile?id=2')[0], 403)
        self.assertEqual(self.call('GET', '/profile', user='bob')[1][0]['name'], 'TEST_BOB')

    def test_orders_owner(self):
        status, orders = self.call('GET', '/orders')
        self.assertEqual(status, 200)
        self.assertTrue(all(order['owner'] == 1 for order in orders))

    def test_sql_injection_ids_rejected(self):
        for path, key in [('/profile', 'id'), ('/assistant/context', 'order_id')]:
            with self.subTest(path=path):
                self.assertEqual(self.call('GET', path + '?' + urlencode({key: '1 OR 1=1'}))[0], 400)

    def test_search_parameterized_even_for_staff(self):
        status, rows = self.call('GET', '/search?' + urlencode({'q': "' OR 1=1--"}), user='staff')
        self.assertEqual(status, 200)
        self.assertEqual(rows, [])

    def test_search_customer_sees_only_self(self):
        status, rows = self.call('GET', '/search?q=TEST')
        self.assertEqual(status, 200)
        self.assertEqual([row['id'] for row in rows], [1])

    def test_staff_privilege_comes_only_from_session(self):
        self.assertEqual(self.call('GET', '/admin/export', user=None, headers={'X-Role': 'staff'})[0], 401)
        self.assertEqual(self.call('GET', '/admin/export', headers={'X-Role': 'staff'})[0], 403)
        self.assertEqual(self.call('GET', '/admin/export', user='staff')[0], 200)
        self.assertEqual(self.call('GET', '/admin/export', user='staff', headers={'X-Role': 'customer'})[0], 200)

    def test_catalog_price_is_authoritative(self):
        for price in [-100, 0, 1, 'free', True]:
            status, order = self.call('POST', '/orders', {'product': 'chair', 'price': price})
            self.assertEqual(status, 201)
            self.assertEqual(order['price'], 5000)

    def test_receipt_authorization_and_internal_paths(self):
        for path in ['/files?user=bob&path=receipt.txt',
                     '/files?' + urlencode({'user': 'alice', 'path': '../../private/operator-note.txt'}),
                     '/files?' + urlencode({'user': '../bob', 'path': 'receipt.txt'})]:
            with self.subTest(path=path):
                self.assertEqual(self.call('GET', path)[0], 403)
        status, result = self.call('GET', '/files?path=receipt.txt', user='bob')
        self.assertEqual(status, 200)
        self.assertIn('TEST_BOB', result['content'])

    def test_assistant_order_owner(self):
        self.assertEqual(self.call('GET', '/assistant/context?order_id=2')[0], 403)

    def test_assistant_has_only_authorized_receipt_tool(self):
        for decision in [
            {'tool': 'export_profiles', 'arguments': {}},
            {'tool': 'read_file', 'arguments': {'path': 'files/bob/receipt.txt'}},
            {'tool': 'read_file', 'arguments': {'path': 'private/operator-note.txt'}},
            {'tool': 'read_file', 'arguments': {'path': 'files/alice/../../private/operator-note.txt'}},
        ]:
            with self.subTest(decision=decision):
                self.assertEqual(self.call('POST', '/assistant/execute', {'decision': decision})[0], 403)

    def test_forced_delete_does_not_change_fixture(self):
        before = self.shop.files()
        status, _ = self.call('POST', '/assistant/execute', {'decision': {'tool': 'delete_tree', 'arguments': {'path': '.'}}})
        self.assertEqual(status, 403)
        self.assertEqual(self.shop.files(), before)

    def test_review_html_is_escaped(self):
        self.assertEqual(self.call('POST', '/reviews', {'product': 'chair', 'text': XSS})[0], 201)
        status, markup = self.call('GET', '/reviews/view')
        self.assertEqual(status, 200)
        self.assertIn(html.escape(XSS), markup)
        self.assertNotIn(XSS, markup)

    def test_logs_privilege_and_secret_redaction(self):
        self.assertEqual(self.call('GET', '/debug/logs')[0], 403)
        status, logs = self.call('GET', '/debug/logs', user='staff')
        self.assertEqual(status, 200)
        text = json.dumps(logs)
        for secret in ['learn-alice', 'learn-bob', *self.shop.tokens.values()]:
            self.assertNotIn(secret, text)

    def test_invalid_json_returns_client_error_without_details(self):
        for raw in [b'{', b'[]', b'null', b'42', b'{"username": NaN}']:
            with self.subTest(raw=raw):
                status, result = self.call('POST', '/login', raw=raw, user=None)
                self.assertEqual(status, 400)
                self.assertNotIn('type', result)

    def test_invalid_shapes_and_fields_are_not_500(self):
        cases = [('/orders', {}), ('/orders', {'product': []}),
                 ('/reviews', {'product': 'chair', 'text': []}),
                 ('/assistant/execute', {'decision': 'bad'}),
                 ('/assistant/execute', {'decision': {'tool': 'read_file', 'arguments': []}})]
        for path, body in cases:
            with self.subTest(path=path, body=body):
                self.assertEqual(self.call('POST', path, body)[0], 400)

    def test_client_workflow_and_refusal_survive_hardening(self):
        self.assertEqual(self.call('GET', '/profile?id=1')[1][0]['name'], 'TEST_ALICE')
        self.assertIn('TEST_ALICE', self.call('GET', '/files?user=alice&path=receipt.txt')[1]['content'])
        self.assertEqual(self.call('POST', '/orders', {'product': 'lamp'})[1]['price'], 1500)
        decision = {'tool': 'read_file', 'arguments': {'path': 'files/alice/receipt.txt'}}
        self.assertIn('TEST_ALICE', self.call('POST', '/assistant/execute', {'decision': decision})[1]['content'])
        self.assertEqual(self.call('POST', '/assistant/execute', {'decision': {'tool': 'refuse', 'arguments': {'reason': 'untrusted review'}}})[0], 200)


if __name__ == '__main__':
    unittest.main()
