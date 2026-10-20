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
import time
from collections import deque
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


#: How many recent frames and messages a trace keeps per socket.
TRACE_KEEP = 40


class SocketTrace:
    """What one socket did, kept only when somebody asked for it.

    Opt-in diagnostics (CI 2026-10-21: every new socket to a live tab failed
    and nothing said whether the browser closed it, the operating system
    aborted it or this side gave up waiting). A trace holds protocol facts
    and nothing else: the handshake's status line and headers, the opcode,
    length and direction of recent frames, the DevTools ids and method names
    of recent messages, the close code and reason the server sent, and the
    operating system's own error on an abort. Never a payload: what travels
    here is somebody's screen.

    Without a trace a socket behaves exactly as it always did; with one it
    only writes into this object.
    """

    def __init__(self, url: str = "", *, keep: int = TRACE_KEEP) -> None:
        self.url = url
        self._began = time.monotonic()
        self.handshake: dict[str, Any] = {}
        self.frames: deque[dict[str, Any]] = deque(maxlen=keep)
        self.messages: deque[dict[str, Any]] = deque(maxlen=keep)
        self.frame_counts = {"in": 0, "out": 0}
        self.server_close: dict[str, Any] | None = None
        self.failure: dict[str, Any] | None = None
        self.closed_by_client_at: float | None = None

    def elapsed(self) -> float:
        return round(time.monotonic() - self._began, 3)

    def frame(self, direction: str, opcode: int, final: bool, length: int) -> None:
        self.frame_counts[direction] += 1
        self.frames.append(
            {"at": self.elapsed(), "dir": direction, "op": opcode, "fin": final, "len": length}
        )

    def message(self, direction: str, *, ident: object = None, method: object = None) -> None:
        entry: dict[str, Any] = {"at": self.elapsed(), "dir": direction}
        if isinstance(ident, int):
            entry["id"] = ident
        if isinstance(method, str):
            entry["method"] = method[:80]
        self.messages.append(entry)

    def closed_by_server(self, payload: bytes) -> None:
        code = struct.unpack(">H", payload[:2])[0] if len(payload) >= 2 else None
        reason = payload[2:].decode("utf-8", errors="replace")[:200]
        self.server_close = {"at": self.elapsed(), "code": code, "reason": reason}

    def failed(self, phase: str, code: str, failure: BaseException | None) -> None:
        """The first failure is the one worth keeping: what follows it is
        usually this side tidying up."""
        if self.failure is not None:
            return
        entry: dict[str, Any] = {"at": self.elapsed(), "phase": phase, "code": code}
        if failure is None:
            entry["os_error"] = "end of stream"
        else:
            entry["os_error"] = type(failure).__name__
            if isinstance(failure, OSError):
                entry["errno"] = failure.errno
                entry["winerror"] = getattr(failure, "winerror", None)
        self.failure = entry

    def as_record(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "lifetime_s": self.elapsed(),
            "handshake": self.handshake,
            "frame_counts": dict(self.frame_counts),
            "frames": list(self.frames),
            "messages": list(self.messages),
            "server_close": self.server_close,
            "failure": self.failure,
            "closed_by_client_at": self.closed_by_client_at,
        }


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

    def __init__(
        self, url: str, *, timeout_s: float = 30.0, trace: SocketTrace | None = None
    ) -> None:
        self.trace = trace
        if trace is not None:
            trace.url = url
        parts = urlsplit(url)
        host = parts.hostname or ""
        if parts.scheme != "ws" or host not in LOOPBACK:
            raise WebSocketError("not_loopback")
        try:
            self.socket = socket.create_connection((host, parts.port or 80), timeout=timeout_s)
        except OSError as failure:
            raise self._failed("connect", "connect_failed", failure) from None
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
            except OSError as failure:
                raise self._failed("handshake", "closed", failure) from None
            if not chunk:
                raise self._failed("handshake", "closed", None)
            head += chunk
            if len(head) > 64 * 1024:
                raise WebSocketError("handshake_wrong")
        header, _, rest = head.partition(b"\r\n\r\n")
        self._held = rest
        lines = header.decode("latin-1").split("\r\n")
        if self.trace is not None:
            self.trace.handshake = {
                "status": lines[0][:200],
                "headers": [line[:200] for line in lines[1:]],
            }
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

    def _failed(
        self, phase: str, code: WebSocketErrorCode, failure: BaseException | None
    ) -> WebSocketError:
        """The error to raise, noted in the trace first when there is one.
        A timeout is an `OSError` too and reads as `closed` to a caller; the
        trace is where the two are told apart."""
        if self.trace is not None:
            self.trace.failed(phase, code, failure)
        return WebSocketError(code)

    # -- frames --------------------------------------------------------

    def _take(self, count: int) -> bytes:
        while len(self._held) < count:
            try:
                chunk = self.socket.recv(65536)
            except OSError as failure:
                raise self._failed("receive", "closed", failure) from None
            if not chunk:
                raise self._failed("receive", "closed", None)
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
        if self.trace is not None:
            self.trace.frame("in", first & 0x0F, bool(first & 0x80), length)
        if length > MAX_MESSAGE_BYTES:
            raise WebSocketError("message_too_large")
        return first & 0x0F, bool(first & 0x80), self._take(length)

    def _send_frame(self, opcode: int, payload: bytes) -> None:
        if self.trace is not None:
            self.trace.frame("out", opcode, True, len(payload))
        try:
            self.socket.sendall(frame(opcode, payload))
        except OSError as failure:
            raise self._failed("send", "closed", failure) from None

    def send(self, text: str) -> None:
        self._send_frame(TEXT, text.encode("utf-8"))

    def receive(self) -> str:
        """One whole message: fragments joined, pings answered, control
        frames never mistaken for content."""
        payload = b""
        opcode = 0
        while True:
            kind, final, chunk = self._read_frame()
            if kind == CLOSE:
                if self.trace is not None:
                    self.trace.closed_by_server(chunk)
                raise self._failed("receive", "closed", None)
            if kind == PING:
                # A pong that cannot be sent is a lost socket like any other,
                # and surfaces as one rather than as a bare OSError that no
                # caller catches.
                self._send_frame(PONG, chunk)
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
        if self.trace is not None and self.trace.closed_by_client_at is None:
            self.trace.closed_by_client_at = self.trace.elapsed()
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

    def __init__(
        self, url: str, *, timeout_s: float = 30.0, trace: SocketTrace | None = None
    ) -> None:
        self.trace = trace
        self.socket = WebSocket(url, timeout_s=timeout_s, trace=trace)
        self._last = 0
        self.events: list[dict[str, Any]] = []

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        self._last += 1
        wanted = self._last
        if self.trace is not None:
            self.trace.message("out", ident=wanted, method=method)
        self.socket.send(json.dumps({"id": wanted, "method": method, "params": params}))
        while True:
            try:
                message = json.loads(self.socket.receive())
            except ValueError:
                raise WebSocketError("protocol_error") from None
            if not isinstance(message, dict):
                raise WebSocketError("protocol_error")
            if self.trace is not None:
                self.trace.message("in", ident=message.get("id"), method=message.get("method"))
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
