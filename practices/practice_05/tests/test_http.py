import http.client
import json
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import unittest
from urllib.parse import urlencode, urlsplit

from app import service
from app.server import create_server


class HTTPContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_root = Path(__file__).resolve().parents[3] / "tmp"
        fixture_root.mkdir(exist_ok=True)
        cls.temp = tempfile.TemporaryDirectory(
            prefix="http-test-", dir=fixture_root
        )
        directory = Path(cls.temp.name)
        for name, content in {
            "index.html": "<!doctype html><title>Subscribers</title>",
            "app.js": "console.log('test');",
            "style.css": "body { color: black; }",
            "secret.txt": "must not be served",
        }.items():
            (directory / name).write_text(content, encoding="utf-8")
        try:
            cls.server = create_server(port=0, static_dir=directory)
        except Exception:
            cls.temp.cleanup()
            raise
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True
        )
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=3)
        cls.temp.cleanup()
        if cls.thread.is_alive():
            raise RuntimeError("HTTP server thread did not stop")

    def setUp(self):
        service.subscribers.clear()
        for name in service.DEMO_NAMES:
            service.subscribe(name)

    def tearDown(self):
        service.subscribers.clear()

    def request(self, path, method="GET"):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        try:
            connection.request(method, path)
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def request_json(self, path, method="GET"):
        status, headers, body = self.request(path, method)
        self.assertEqual(headers["Content-Type"], "application/json; charset=utf-8")
        self.assertEqual(int(headers["Content-Length"]), len(body))
        return status, headers, json.loads(body.decode("utf-8"))

    def test_full_list_missing_and_empty_q(self):
        for path in ("/api/subscribers", "/api/subscribers?q="):
            with self.subTest(path=path):
                status, _, payload = self.request_json(path)
                self.assertEqual(status, 200)
                self.assertEqual(payload, {"query": "", "items": ["Alice", "Bob", "Анна", "Борис"], "total": 4})

    def test_search_utf8_and_normalized_query(self):
        for query, normalized, expected in (
            ("  ALI  ", "ALI", ["Alice"]),
            ("АН", "АН", ["Анна"]),
            ("\u001cALI\u001c", "ALI", ["Alice"]),
            ("zzz", "zzz", []),
            ("   ", "", ["Alice", "Bob", "Анна", "Борис"]),
        ):
            with self.subTest(query=query):
                status, _, payload = self.request_json("/api/subscribers?" + urlencode({"q": query}))
                self.assertEqual(status, 200)
                self.assertEqual(payload, {"query": normalized, "items": expected, "total": len(expected)})

    def test_empty_storage(self):
        service.subscribers.clear()
        status, _, payload = self.request_json("/api/subscribers")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"query": "", "items": [], "total": 0})

    def test_code_point_boundary_and_recovery(self):
        for length in (100, 101):
            status, _, payload = self.request_json(
                "/api/subscribers?" + urlencode({"q": "\U0001f600" * length})
            )
            if length == 100:
                self.assertEqual(status, 200)
                self.assertEqual(payload["total"], 0)
            else:
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["code"], "query_too_long")
                self.assertIn("100", payload["error"]["message"])
        status, _, payload = self.request_json("/api/subscribers?q=Alice")
        self.assertEqual(status, 200)
        self.assertEqual(payload["items"], ["Alice"])

    def test_unknown_duplicate_and_malformed_query(self):
        for query in ("q=a&q=b", "q=a&q=", "query=Alice", "q=a&extra=b", "q=%", "q=%GG", "q=%FF", "q=%C0%AF", "q=%ED%A0%80"):
            with self.subTest(query=query):
                status, _, payload = self.request_json("/api/subscribers?" + query)
                self.assertEqual(status, 400)
                self.assertEqual(payload["error"]["code"], "invalid_query")

    def test_unsupported_api_methods(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                status, headers, payload = self.request_json("/api/subscribers", method)
                self.assertEqual(status, 405)
                self.assertEqual(headers["Allow"], "GET")
                self.assertEqual(payload["error"]["code"], "method_not_allowed")

    def test_static_allowlist_and_content_types(self):
        for path, expected_type in (("/", "text/html"), ("/app.js", "text/javascript"), ("/style.css", "text/css")):
            with self.subTest(path=path):
                status, headers, body = self.request(path)
                self.assertEqual(status, 200)
                self.assertEqual(headers["Content-Type"], expected_type + "; charset=utf-8")
                self.assertTrue(body)

    def test_unknown_routes_and_traversal_not_served(self):
        for path in ("/missing", "/api/missing", "/secret.txt", "/../secret.txt", "/%2e%2e/secret.txt", "/app/service.py"):
            with self.subTest(path=path):
                status, _, payload = self.request_json(path)
                self.assertEqual(status, 404)
                self.assertEqual(payload["error"]["code"], "not_found")

    def test_api_returns_name_as_json_data(self):
        name = "<img src=x onerror=alert(1)>"
        service.subscribe(name)
        status, _, payload = self.request_json("/api/subscribers?" + urlencode({"q": "<img"}))
        self.assertEqual(status, 200)
        self.assertEqual(payload["items"], [name])


class CLIStartupTests(unittest.TestCase):
    def test_actual_port_url_and_explicit_demo_flag(self):
        for demo in (False, True):
            with self.subTest(demo=demo):
                command = [sys.executable, "-m", "app.server", "--host", "127.0.0.1", "--port", "0"]
                if demo:
                    command.append("--demo")
                process = subprocess.Popen(
                    command,
                    cwd=Path(__file__).resolve().parents[1],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                )
                lines = queue.Queue()
                reader = threading.Thread(target=lambda: lines.put(process.stdout.readline()), daemon=True)
                reader.start()
                try:
                    try:
                        url = lines.get(timeout=5).strip()
                    except queue.Empty:
                        self.fail("Server did not print its URL within five seconds")
                    address = urlsplit(url)
                    self.assertEqual(address.scheme, "http")
                    self.assertEqual(address.hostname, "127.0.0.1")
                    self.assertGreater(address.port or 0, 0)
                    connection = http.client.HTTPConnection(address.hostname, address.port, timeout=3)
                    try:
                        connection.request("GET", "/api/subscribers")
                        response = connection.getresponse()
                        self.assertEqual(response.status, 200)
                        payload = json.loads(response.read().decode("utf-8"))
                    finally:
                        connection.close()
                    expected = ["Alice", "Bob", "Анна", "Борис"] if demo else []
                    self.assertEqual(payload["items"], expected)
                    self.assertEqual(payload["total"], len(expected))
                finally:
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=3)
                    reader.join(timeout=1)
                    process.stdout.close()
                    process.stderr.close()


if __name__ == "__main__":
    unittest.main()
