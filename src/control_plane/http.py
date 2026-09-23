"""The control-plane service over HTTP, from the standard library alone.

`POST /v1/<operation>` with `Authorization: Bearer <token_id>:<secret>`, JSON
in and JSON out. One `GET /v1/health` answers without a token and says only
that the process is up. The server follows no redirect, logs no request,
names no software in its headers, and echoes nothing a Bridge sent: a refusal
is a `WireFailure` code with the status the service assigns it.

Deliberately small. The pinned Host Bridge was a FastAPI application behind
`requests`; the platform's install is `pydantic` alone, and this wire is six
operations, so the standard library's server is enough and adds nothing to
carry.
"""

import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self

from common.base import Contract
from common.sync import WireFailure
from control_plane.service import STATUS_FOR, ControlPlaneService, ServiceError

API_PREFIX = "/v1/"
# A sync reply carries manifests, which are small; a request never carries
# more than a snapshot. Anything larger is not this wire.
MAX_BODY_BYTES = 4 * 1024 * 1024
BEARER = "Bearer "


def _credential(header: str | None) -> tuple[str, str] | None:
    """`(token_id, secret)` from the header, or None when it is not one. A
    Symbol never contains a colon and a generated secret never does either,
    so the first colon is the only place the two can meet."""
    if header is None or not header.startswith(BEARER):
        return None
    value = header[len(BEARER) :].strip()
    token_id, separator, secret = value.partition(":")
    if not separator or not token_id or not secret:
        return None
    return token_id, secret


def _failure(code: Any) -> tuple[int, bytes]:
    failure = WireFailure(code=code, retryable=STATUS_FOR[code] >= 500)
    return STATUS_FOR[code], failure.model_dump_json().encode("utf-8")


class _Handler(BaseHTTPRequestHandler):
    """One request. The service is found on the server; the handler holds
    nothing of its own and never keeps the credential past the call."""

    server: "ControlPlaneServer"  # noqa: UP037 - the class is defined below
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - base signature
        return None

    def version_string(self) -> str:
        return "control-plane"

    def _send(self, status: int, body: bytes, *, unread_body: bool = False) -> None:
        # One request per connection. A refusal sent before the body was
        # read would otherwise leave that body on the wire to be parsed as
        # the next request, and every operation here is one round trip.
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        if unread_body:
            self._linger()

    def _linger(self, *, seconds: float = 0.25, limit: int = 65536) -> None:
        """Swallow what the client already sent before closing on it.

        A socket closed with data still unread is reset rather than finished,
        and a reset discards whatever the client has not yet picked up --
        including the refusal just written. Only the paths that refuse
        *before* reading a declared body need this, and it is bounded by
        time as well as by size, because the declared length is exactly what
        those paths refused to believe."""
        try:
            self.wfile.flush()
            self.connection.settimeout(seconds)
            while limit > 0:
                chunk = self.connection.recv(min(limit, 8192))
                if not chunk:
                    return
                limit -= len(chunk)
        except OSError:
            return

    def _refuse(self, code: Any, *, unread_body: bool = False) -> None:
        status, body = _failure(code)
        self._send(status, body, unread_body=unread_body)

    def do_GET(self) -> None:  # noqa: N802 - the base class names it
        if self.path == f"{API_PREFIX}health":
            self._send(200, b'{"ok":true}')
            return
        self._refuse("unknown_operation")

    def do_POST(self) -> None:  # noqa: N802 - the base class names it
        if not self.path.startswith(API_PREFIX):
            self._refuse("unknown_operation")
            return
        operation = self.path[len(API_PREFIX) :]
        if self.headers.get("Transfer-Encoding"):
            # A body of unstated length is not read; this wire states it.
            self._refuse("invalid_request", unread_body=True)
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._refuse("invalid_request")
            return
        if length < 0 or length > MAX_BODY_BYTES:
            # Refused before it is read: a body that large is not read at all.
            self._refuse("request_too_large", unread_body=True)
            return
        raw = self.rfile.read(length) if length else b""
        credential = _credential(self.headers.get("Authorization"))
        if credential is None:
            self._refuse("authentication_failed")
            return
        try:
            body: object = json.loads(raw) if raw else {}
        except ValueError:
            self._refuse("invalid_request")
            return
        try:
            reply: Contract = self.server.service.handle(operation, *credential, body)
        except ServiceError as error:
            self._refuse(error.code)
            return
        except Exception:  # noqa: BLE001 - never a traceback over the wire
            # Including a contract the service could not build while
            # answering: that is the platform's own inconsistency, reported
            # as such and retryable, never as the Bridge's request.
            self._refuse("internal_error")
            return
        self._send(200, reply.model_dump_json().encode("utf-8"))


class ControlPlaneServer(ThreadingHTTPServer):
    """The service on a socket. Port 0 takes a free one, which is what a
    test wants; an operator names the port. Given an `ssl.SSLContext` the
    socket is wrapped with it, which is how a platform reached over the
    network is expected to be served."""

    daemon_threads = True
    allow_reuse_address = False

    def __init__(
        self,
        service: ControlPlaneService,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self.service = service
        super().__init__((host, port), _Handler)
        if ssl_context is not None:
            self.socket = ssl_context.wrap_socket(self.socket, server_side=True)
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        host, port = self.server_address[0], self.server_address[1]
        name = host.decode("ascii") if isinstance(host, bytes) else str(host)
        if ":" in name:  # an IPv6 address is bracketed in a URL
            name = f"[{name}]"
        scheme = "https" if isinstance(self.socket, ssl.SSLSocket) else "http"
        return f"{scheme}://{name}:{port}"

    def start(self) -> Self:
        """Serve on a background thread, so a test or an operator's process
        keeps its own thread for itself."""
        if self._thread is None:
            self._thread = threading.Thread(target=self.serve_forever, daemon=True)
            self._thread.start()
        return self

    def stop(self) -> None:
        if self._thread is not None:
            self.shutdown()
            self._thread.join(timeout=5)
            self._thread = None
        self.server_close()

    def __enter__(self) -> Self:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.stop()
