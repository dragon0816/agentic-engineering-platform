"""Local fixture HTTP server for coding_v1 (web tasks T10-T13, mock service T09).

Runs inside the evaluator's process on 127.0.0.1. Every request is logged so
validators can check what the Agent actually fetched. The T09 scenario is set
by the evaluator through `set_scenario`, never over HTTP, so the Agent cannot
change it.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parent / "web"
ROUTES = {
    "/t10/catalog": "t10/catalog.html",
    "/t11/list": "t11/list.html",
    "/t12/a": "t12/a.html",
    "/t12/b": "t12/b.html",
    "/t12/c": "t12/c.html",
    "/t13/list": "t13/list.html",
    **{f"/t11/item/{n}": f"t11/item{n}.html" for n in range(1, 5)},
    **{f"/t13/item/{n}": f"t13/item{n}.html" for n in (1, 2, 3, 4)},
}


class FixtureServer:
    def __init__(self) -> None:
        self.log: list[dict[str, object]] = []
        self.scenario = "succeed_third"
        self.login_calls = 0
        self.tokens: set[str] = set()
        self._lock = threading.Lock()
        server = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: object) -> None:  # noqa: A002
                return

            def _reply(self, status: int, body: bytes, kind: str) -> None:
                self.send_response(status)
                self.send_header("Content-Type", kind)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _record(self, status: int) -> None:
                with server._lock:
                    server.log.append(
                        {
                            "t": time.time(),
                            "method": self.command,
                            "path": self.path,
                            "status": status,
                        }
                    )

            def do_GET(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0]
                if path == "/t13/item/5":
                    self._record(500)
                    self._reply(500, b"internal error", "text/plain")
                    return
                if path == "/t09/data":
                    token = (self.headers.get("Authorization") or "").removeprefix("Bearer ")
                    ok = token in server.tokens
                    self._record(200 if ok else 401)
                    body = json.dumps(
                        {"items": [{"id": "A1", "value": 42}, {"id": "A2", "value": 7}]}
                        if ok
                        else {"error": "unauthorized"}
                    )
                    self._reply(200 if ok else 401, body.encode(), "application/json")
                    return
                page = ROUTES.get(path)
                if page is None:
                    self._record(404)
                    self._reply(404, b"not found", "text/plain")
                    return
                self._record(200)
                self._reply(200, (WEB / page).read_bytes(), "text/html; charset=utf-8")

            def do_POST(self) -> None:  # noqa: N802
                path = self.path.split("?", 1)[0]
                length = int(self.headers.get("Content-Length") or 0)
                self.rfile.read(length)
                if path != "/t09/login":
                    self._record(404)
                    self._reply(404, b"not found", "text/plain")
                    return
                with server._lock:
                    server.login_calls += 1
                    attempt = server.login_calls
                ok = server.scenario == "succeed_third" and attempt >= 3
                body: dict[str, object] = {"ok": ok}
                if ok:
                    token = secrets.token_hex(8)
                    server.tokens.add(token)
                    body["token"] = token
                else:
                    body["reason"] = "invalid credentials (scripted)"
                self._record(200)
                self._reply(200, json.dumps(body).encode(), "application/json")

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._server.server_address[1]}"

    def start(self) -> None:
        threading.Thread(target=self._server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def set_scenario(self, name: str) -> None:
        """`succeed_third` or `always_fail`; resets the login counter."""
        with self._lock:
            self.scenario = name
            self.login_calls = 0
            self.tokens.clear()

    def requests(self, prefix: str) -> list[dict[str, object]]:
        with self._lock:
            return [item for item in self.log if str(item["path"]).startswith(prefix)]
