"""Standard-library HTTP server for the subscriber-search contract."""

import argparse
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from urllib.parse import parse_qsl, urlsplit

from . import service


API_PATH = "/api/subscribers"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}
INVALID_PERCENT = re.compile(r"%(?![0-9a-fA-F]{2})")


def parse_query(raw_query: str) -> str:
    """Decode UTF-8 strictly and reject ambiguous or unknown parameters."""
    try:
        if INVALID_PERCENT.search(raw_query):
            raise ValueError("invalid percent escape")
        pairs = parse_qsl(
            raw_query,
            keep_blank_values=True,
            strict_parsing=True,
            encoding="utf-8",
            errors="strict",
            max_num_fields=2,
        )
        if len(pairs) > 1 or any(key != "q" for key, _ in pairs):
            raise ValueError("expected at most one q parameter")
    except (ValueError, UnicodeError) as exc:
        raise service.QueryError(
            "invalid_query", "Некорректные параметры поискового запроса."
        ) from exc
    return service.normalize_query(pairs[0][1] if pairs else "")


class SubscriberRequestHandler(BaseHTTPRequestHandler):
    def __init__(self, *args, static_dir: Path, **kwargs):
        self.static_dir = static_dir
        super().__init__(*args, **kwargs)

    def log_message(self, format, *args):
        # Keep stdout reserved for the startup URL; tests inspect HTTP responses.
        pass

    def _send_bytes(self, status: int, body: bytes, content_type: str, headers=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, status: int, payload: dict, headers=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._send_bytes(status, body, "application/json; charset=utf-8", headers)

    def _error(self, status: int, code: str, message: str, headers=None):
        self._json(status, {"error": {"code": code, "message": message}}, headers)

    def do_GET(self):
        try:
            target = urlsplit(self.path)
        except ValueError:
            self._error(400, "invalid_query", "Некорректный адрес запроса.")
            return
        if target.path == API_PATH:
            try:
                query = parse_query(target.query)
                items = service.search_subscribers(query)
            except service.QueryError as exc:
                self._error(400, exc.code, str(exc))
                return
            self._json(200, {"query": query, "items": items, "total": len(items)})
            return

        resource = STATIC_FILES.get(target.path)
        if resource is None:
            self._error(404, "not_found", "Ресурс не найден.")
            return
        filename, content_type = resource
        try:
            body = (self.static_dir / filename).read_bytes()
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            self._error(404, "not_found", "Ресурс не найден.")
            return
        self._send_bytes(200, body, content_type)

    def _unsupported_method(self):
        try:
            path = urlsplit(self.path).path
        except ValueError:
            path = ""
        if path == API_PATH or path in STATIC_FILES:
            self._error(
                405,
                "method_not_allowed",
                "Для этого ресурса разрешён только GET.",
                {"Allow": "GET"},
            )
        else:
            self._error(404, "not_found", "Ресурс не найден.")

    do_POST = _unsupported_method
    do_PUT = _unsupported_method
    do_PATCH = _unsupported_method
    do_DELETE = _unsupported_method
    do_HEAD = _unsupported_method
    do_OPTIONS = _unsupported_method


def create_server(
    host: str = "127.0.0.1", port: int = 8765, static_dir: Path | None = None
) -> ThreadingHTTPServer:
    directory = Path(static_dir) if static_dir is not None else Path(__file__).with_name("static")
    handler = partial(SubscriberRequestHandler, static_dir=directory)
    return ThreadingHTTPServer((host, port), handler)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Локальный поиск подписчиков")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--demo", action="store_true", help="Добавить четыре демонстрационных имени")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("--port должен быть в диапазоне 0..65535")
    service.subscribers.clear()
    if args.demo:
        for name in service.DEMO_NAMES:
            service.subscribe(name)
    with create_server(args.host, args.port) as server:
        print(f"http://{args.host}:{server.server_address[1]}", flush=True)
        try:
            server.serve_forever(poll_interval=0.1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
