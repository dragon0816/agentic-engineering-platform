"""A local fake of the Telegram Bot API over real HTTP (docs/phases/VOICE_INPUT.md
§4.5), for driving `TelegramIngress` end to end without Telegram.

The ingress keeps its production `api_base` (`https://api.telegram.org`,
which its config validator requires); `ForwardingTransport` sends what would
go there to this server on `http://127.0.0.1:<port>` instead, without a proxy.
Served: `getUpdates`, `getFile`, file download by GET, `sendMessage`,
`editMessageText`, `answerCallbackQuery`, and `ok` for any other method.
"""

from __future__ import annotations

import json
import threading
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from models.wire import Reply, UrllibTransport

TELEGRAM = "https://api.telegram.org"


@dataclass
class BotState:
    token: str
    updates: list[dict[str, Any]] = field(default_factory=list)
    files: dict[str, bytes] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    downloads: list[str] = field(default_factory=list)
    # (message id, sendMessage payload) of every message the bot sent.
    sent: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
    next_message_id: int = 100
    lock: threading.Lock = field(default_factory=threading.Lock)

    def said(self) -> list[str]:
        """Every text sent or edited into the chat, in order."""
        return [
            str(payload["text"])
            for method, payload in self.calls
            if method in ("sendMessage", "editMessageText") and "text" in payload
        ]

    def methods(self) -> list[str]:
        return [method for method, _ in self.calls]

    def last_keyboard(self) -> int:
        """The id of the newest message sent with buttons."""
        return [number for number, payload in self.sent if "reply_markup" in payload][-1]


class _Handler(BaseHTTPRequestHandler):
    server: _Server

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib name
        return None

    def _answer(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib name
        state = self.server.state
        prefix = f"/file/bot{state.token}/"
        if not self.path.startswith(prefix):
            self._answer(401, {"ok": False, "description": "Unauthorized"})
            return
        file_path = self.path[len(prefix) :]
        file_id = file_path.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        data = state.files.get(file_id)
        with state.lock:
            state.downloads.append(file_path)
        if data is None:
            self._answer(404, {"ok": False, "description": "Not Found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:  # noqa: N802 - stdlib name
        state = self.server.state
        prefix = f"/bot{state.token}/"
        if not self.path.startswith(prefix):
            self._answer(401, {"ok": False, "description": "Unauthorized"})
            return
        method = self.path[len(prefix) :]
        length = int(self.headers.get("Content-Length") or 0)
        payload = json.loads(self.rfile.read(length) or b"{}")
        with state.lock:
            state.calls.append((method, payload))
            result = self._result(state, method, payload)
        self._answer(200, {"ok": True, "result": result})

    @staticmethod
    def _result(state: BotState, method: str, payload: Mapping[str, Any]) -> object:
        if method == "getUpdates":
            offset = int(payload.get("offset") or 0)
            ready = [item for item in state.updates if item["update_id"] >= offset]
            state.updates = ready
            return ready
        if method == "getFile":
            file_id = str(payload.get("file_id"))
            if file_id not in state.files:
                return None
            return {
                "file_id": file_id,
                "file_unique_id": f"u-{file_id}",
                "file_size": len(state.files[file_id]),
                "file_path": f"voice/{file_id}.oga",
            }
        if method in ("sendMessage", "editMessageText"):
            state.next_message_id += 1
            number = int(payload.get("message_id") or state.next_message_id)
            if method == "sendMessage":
                state.sent.append((number, dict(payload)))
            return {
                "message_id": number,
                "chat": {"id": payload.get("chat_id"), "type": "private"},
                "date": 0,
                "text": payload.get("text", ""),
            }
        return True


class _Server(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, state: BotState) -> None:
        super().__init__(("127.0.0.1", 0), _Handler)
        self.state = state


class FakeBotApi:
    """`with FakeBotApi(token) as bot:` serves until the block ends."""

    def __init__(self, token: str) -> None:
        self.state = BotState(token)
        self._server = _Server(self.state)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def origin(self) -> str:
        host, port = self._server.server_address[:2]
        return f"http://{host!s}:{port}"

    def __enter__(self) -> FakeBotApi:
        self._thread.start()
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join(5)

    def push(self, *updates: dict[str, Any]) -> None:
        with self.state.lock:
            self.state.updates.extend(updates)

    def transport(self) -> ForwardingTransport:
        return ForwardingTransport(self.origin)


class ForwardingTransport(UrllibTransport):
    """The production transport, with Telegram's origin sent to the fake
    server and no proxy (the company proxy must not see a loopback call)."""

    def __init__(self, origin: str) -> None:
        super().__init__((urllib.request.ProxyHandler({}),))
        self.origin = origin

    def request(
        self,
        method: str,
        url: str,
        body: bytes | None,
        headers: Mapping[str, str],
        timeout_s: float,
    ) -> Reply:
        if not url.startswith(TELEGRAM + "/"):
            raise AssertionError("only the Bot API is forwarded")
        return super().request(method, self.origin + url[len(TELEGRAM) :], body, headers, 5.0)
