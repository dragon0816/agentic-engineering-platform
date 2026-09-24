"""A WebSocket client small enough to keep, for talking to a browser.

The browser this machine already has speaks the Chrome DevTools Protocol, and
its HTTP endpoints list targets and nothing else: every command goes over a
WebSocket. The standard library has no client for one, and the alternative --
a browser automation library that downloads its own browser -- is hundreds of
megabytes into an offline bundle installed with `--no-index`, on a bundle that
has already had one install fail for a path that was too long.

So this is RFC 6455's client half and no more: connect, mask what it sends,
reassemble what arrives, answer a ping. No extension and no compression is
negotiated, so no frame ever arrives compressed and there is no negotiation
to get wrong.

It connects to the loopback address only, which is where a browser this
machine started listens. There is therefore no TLS here and none is wanted:
a certificate for 127.0.0.1 would be ceremony, and accepting one for anything
else would be the hole this refuses to have.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import socket
import struct
from types import TracebackType
from typing import Any, Literal, Self
from urllib.parse import urlsplit

#: RFC 6455's constant, concatenated with the key to prove the server spoke
#: WebSocket rather than echoing something.
GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
TEXT, BINARY, CLOSE, PING, PONG = 0x1, 0x2, 0x8, 0x9, 0xA
LOOPBACK = ("127.0.0.1", "localhost", "::1")
#: A screenshot arrives as base64 in one message and a large page's element
#: list is not small either, but nothing here is a file transfer. Past this a
#: message is refused rather than held.
MAX_MESSAGE_BYTES = 64 * 1024 * 1024

WebSocketErrorCode = Literal[
    "not_loopback",
    "connect_failed",
    "handshake_refused",
    "handshake_wrong",
    "closed",
    "protocol_error",
    "message_too_large",
]


class WebSocketError(Exception):
    """The code is the whole message. What travels on this socket is the
    content of somebody's screen, so nothing from the wire is echoed."""

    def __init__(self, code: WebSocketErrorCode) -> None:
        self.code: WebSocketErrorCode = code
        super().__init__(code)


def accept_for(key: str) -> str:
    """What a server must answer a given key with."""
    return base64.b64encode(hashlib.sha1((key + GUID).encode()).digest()).decode()


def frame(opcode: int, payload: bytes, *, mask: bytes | None = None) -> bytes:
    """One whole frame. A client masks every frame it sends; `mask` is taken
    rather than generated only so a test can pin the masking."""
    header = bytearray([0x80 | opcode])
    length = len(payload)
    masking = mask if mask is not None else os.urandom(4)
    if length < 126:
        header.append(0x80 | length)
    elif length < 1 << 16:
        header.append(0x80 | 126)
        header += struct.pack(">H", length)
    else:
        header.append(0x80 | 127)
        header += struct.pack(">Q", length)
    header += masking
    return bytes(header) + bytes(byte ^ masking[index % 4] for index, byte in enumerate(payload))


class WebSocket:
    """One connection, to this machine and nowhere else."""

    def __init__(self, url: str, *, timeout_s: float = 30.0) -> None:
        parts = urlsplit(url)
        host = parts.hostname or ""
        if parts.scheme != "ws" or host not in LOOPBACK:
            raise WebSocketError("not_loopback")
        try:
            self.socket = socket.create_connection((host, parts.port or 80), timeout=timeout_s)
        except OSError:
            raise WebSocketError("connect_failed") from None
        self.socket.settimeout(timeout_s)
        self._held = b""
        try:
            self._handshake(host, parts.port or 80, parts.path or "/")
        except Exception:
            self.close()
            raise

    def _handshake(self, host: str, port: int, path: str) -> None:
        key = base64.b64encode(os.urandom(16)).decode()
        self.socket.sendall(
            (
                f"GET {path} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                "Upgrade: websocket\r\n"
                "Connection: Upgrade\r\n"
                f"Sec-WebSocket-Key: {key}\r\n"
                "Sec-WebSocket-Version: 13\r\n\r\n"
            ).encode()
        )
        head = b""
        while b"\r\n\r\n" not in head:
            try:
                chunk = self.socket.recv(4096)
            except OSError:
                raise WebSocketError("closed") from None
            if not chunk:
                raise WebSocketError("closed")
            head += chunk
            if len(head) > 64 * 1024:
                raise WebSocketError("handshake_wrong")
        header, _, rest = head.partition(b"\r\n\r\n")
        self._held = rest
        lines = header.decode("latin-1").split("\r\n")
        if " 101" not in lines[0]:
            raise WebSocketError("handshake_refused")
        answered = next(
            (
                line.split(":", 1)[1].strip()
                for line in lines[1:]
                if line.lower().startswith("sec-websocket-accept:")
            ),
            "",
        )
        if answered != accept_for(key):
            # Something is listening there and it is not a WebSocket server,
            # which is worth telling apart from a refusal.
            raise WebSocketError("handshake_wrong")

    # -- frames --------------------------------------------------------

    def _take(self, count: int) -> bytes:
        while len(self._held) < count:
            try:
                chunk = self.socket.recv(65536)
            except OSError:
                raise WebSocketError("closed") from None
            if not chunk:
                raise WebSocketError("closed")
            self._held += chunk
        taken, self._held = self._held[:count], self._held[count:]
        return taken

    def _read_frame(self) -> tuple[int, bool, bytes]:
        first, second = self._take(2)
        if second & 0x80:
            # A server frame is never masked; one that is means this is not
            # the protocol it claims to be.
            raise WebSocketError("protocol_error")
        length = second & 0x7F
        if length == 126:
            (length,) = struct.unpack(">H", self._take(2))
        elif length == 127:
            (length,) = struct.unpack(">Q", self._take(8))
        if length > MAX_MESSAGE_BYTES:
            raise WebSocketError("message_too_large")
        return first & 0x0F, bool(first & 0x80), self._take(length)

    def send(self, text: str) -> None:
        try:
            self.socket.sendall(frame(TEXT, text.encode("utf-8")))
        except OSError:
            raise WebSocketError("closed") from None

    def receive(self) -> str:
        """One whole message: fragments joined, pings answered, control
        frames never mistaken for content."""
        payload = b""
        opcode = 0
        while True:
            kind, final, chunk = self._read_frame()
            if kind == CLOSE:
                raise WebSocketError("closed")
            if kind == PING:
                self.socket.sendall(frame(PONG, chunk))
                continue
            if kind == PONG:
                continue
            if kind in (TEXT, BINARY):
                opcode, payload = kind, chunk
            elif kind == 0:
                payload += chunk
            else:
                raise WebSocketError("protocol_error")
            if len(payload) > MAX_MESSAGE_BYTES:
                raise WebSocketError("message_too_large")
            if final:
                break
        if opcode == BINARY:
            raise WebSocketError("protocol_error")
        return payload.decode("utf-8", errors="replace")

    def close(self) -> None:
        try:
            self.socket.sendall(frame(CLOSE, b""))
        except (OSError, AttributeError):
            pass
        try:
            self.socket.close()
        except (OSError, AttributeError):
            pass

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class Devtools:
    """One browser target, spoken to in Chrome DevTools Protocol.

    A command is an id, a method and its parameters; the answer carries the
    same id. Anything else arriving in between is an event the browser sent
    unasked, which is kept rather than dropped: `Page.loadEventFired` is how
    this knows a navigation finished.
    """

    def __init__(self, url: str, *, timeout_s: float = 30.0) -> None:
        self.socket = WebSocket(url, timeout_s=timeout_s)
        self._last = 0
        self.events: list[dict[str, Any]] = []

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        self._last += 1
        wanted = self._last
        self.socket.send(json.dumps({"id": wanted, "method": method, "params": params}))
        while True:
            try:
                message = json.loads(self.socket.receive())
            except ValueError:
                raise WebSocketError("protocol_error") from None
            if not isinstance(message, dict):
                raise WebSocketError("protocol_error")
            if message.get("id") != wanted:
                self.events.append(message)
                continue
            if "error" in message:
                # The browser's own words about a command, not about content.
                raise DevtoolsRefused(method, str(message["error"].get("message", "")))
            result = message.get("result")
            return result if isinstance(result, dict) else {}

    def drain(self, method: str) -> bool:
        """Whether an event of this name has already arrived."""
        return any(event.get("method") == method for event in self.events)

    def close(self) -> None:
        self.socket.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class DevtoolsRefused(Exception):
    """A command the browser would not run. The method is named and the
    browser's message is kept, because it describes the command rather than
    the page: `Runtime.evaluate` failing is about the expression, not about
    what was on screen."""

    def __init__(self, method: str, detail: str) -> None:
        self.method = method
        self.detail = detail
        super().__init__(f"{method}: {detail}" if detail else method)
