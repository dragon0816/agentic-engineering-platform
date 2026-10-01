"""Standard-library HTTP entry point for authenticated platform members."""

from __future__ import annotations

import json
import ssl
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self

from pydantic import ValidationError

from common.base import Contract
from common.identity import IssuedInvitationProof
from common.member import (
    MemberCatalogRequest,
    MemberReplaceRequest,
    MemberRevokeRequest,
    MemberSelectRequest,
)
from control_plane.member import IssuedMemberSession, MemberError, MemberService
from control_plane.member_page import PAGE
from control_plane.member_signin import InMemoryInvitationSignIn, InvitationSignInError

API_PREFIX = "/v1/member/"
MAX_BODY_BYTES = 256 * 1024
BEARER = "Bearer "
INVITATION = "Invitation "

STATUS_FOR = {
    "authentication_failed": 401,
    "session_expired": 401,
    "actor_mismatch": 403,
    "actor_unknown": 403,
    "actor_disabled": 403,
    "actor_not_admitted": 403,
    "asset_not_published": 404,
    "asset_not_entitled": 403,
    "kind_mismatch": 409,
    "duplicate_selection": 409,
    "selection_missing": 404,
    "decision_in_future": 400,
    "invalid_request": 400,
    "invitation_expired": 401,
    "invitation_used": 409,
    "invitation_revoked": 401,
}


def _credential(header: str | None) -> tuple[str, str] | None:
    if header is None or not header.startswith(BEARER):
        return None
    session_id, separator, secret = header[len(BEARER) :].strip().partition(":")
    if not separator or not session_id or not secret:
        return None
    return session_id, secret


def _invitation_credential(header: str | None) -> tuple[str, str] | None:
    if header is None or not header.startswith(INVITATION):
        return None
    invitation_id, separator, secret = header[len(INVITATION) :].strip().partition(":")
    if not separator or not invitation_id or not secret:
        return None
    return invitation_id, secret


class _Handler(BaseHTTPRequestHandler):
    server: "MemberPortalServer"  # noqa: UP037
    protocol_version = "HTTP/1.1"

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return None

    def _send(self, status: int, body: bytes, kind: str = "application/json") -> None:
        self.close_connection = True
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: object) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/":
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
        elif self.path == f"{API_PREFIX}health":
            self._json(200, {"ok": True})
        else:
            self._json(404, {"code": "invalid_request"})

    def do_POST(self) -> None:  # noqa: N802
        operation = self.path.removeprefix(API_PREFIX) if self.path.startswith(API_PREFIX) else ""
        if operation not in ("sign-in", "catalog", "select", "replace", "revoke"):
            self._json(404, {"code": "invalid_request"})
            return
        if operation == "sign-in":
            self._sign_in()
            return
        credential = _credential(self.headers.get("Authorization"))
        if credential is None:
            self._json(401, {"code": "authentication_failed"})
            return
        if self.headers.get("Transfer-Encoding"):
            self._json(400, {"code": "invalid_request"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._json(400, {"code": "invalid_request"})
            return
        if length < 0 or length > MAX_BODY_BYTES:
            self._json(413, {"code": "invalid_request"})
            return
        try:
            raw: object = json.loads(self.rfile.read(length)) if length else {}
            reply: Contract
            if operation == "catalog":
                reply = self.server.service.catalog(
                    *credential, MemberCatalogRequest.model_validate(raw)
                )
            elif operation == "select":
                reply = self.server.service.select(
                    *credential, MemberSelectRequest.model_validate(raw)
                )
            elif operation == "replace":
                reply = self.server.service.replace(
                    *credential, MemberReplaceRequest.model_validate(raw)
                )
            else:
                reply = self.server.service.revoke(
                    *credential, MemberRevokeRequest.model_validate(raw)
                )
        except (ValidationError, ValueError):
            self._json(400, {"code": "invalid_request"})
            return
        except MemberError as error:
            self._json(STATUS_FOR[error.code], {"code": error.code})
            return
        except Exception:  # noqa: BLE001 - no traceback crosses the member boundary
            self._json(500, {"code": "internal_error"})
            return
        self._send(200, reply.model_dump_json().encode("utf-8"))

    def _sign_in(self) -> None:
        credential = _invitation_credential(self.headers.get("Authorization"))
        if credential is None or self.server.sign_in is None:
            self._json(401, {"code": "authentication_failed"})
            return
        if self.headers.get("Transfer-Encoding"):
            self._json(400, {"code": "invalid_request"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            self._json(400, {"code": "invalid_request"})
            return
        if length != 0:
            self._json(400, {"code": "invalid_request"})
            return
        try:
            session = self.server.sign_in.accept(*credential)
        except InvitationSignInError as error:
            self._json(STATUS_FOR[error.code], {"code": error.code})
            return
        except Exception:  # noqa: BLE001 - no traceback crosses the sign-in boundary
            self._json(500, {"code": "internal_error"})
            return
        self._json(
            200,
            {"session": session.bearer, "expires_at": session.grant.expires_at.isoformat()},
        )


class MemberPortalServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(
        self,
        service: MemberService,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        ssl_context: ssl.SSLContext | None = None,
        sign_in: InMemoryInvitationSignIn | None = None,
    ) -> None:
        if ssl_context is None and host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("a member portal exposed beyond loopback requires TLS")
        self.service = service
        self.sign_in = sign_in
        super().__init__((host, port), _Handler)
        if ssl_context is not None:
            self.socket = ssl_context.wrap_socket(self.socket, server_side=True)
        self._thread: threading.Thread | None = None

    @property
    def base_url(self) -> str:
        host, port = self.server_address[0], self.server_address[1]
        name = host.decode("ascii") if isinstance(host, bytes) else str(host)
        if ":" in name:
            name = f"[{name}]"
        scheme = "https" if isinstance(self.socket, ssl.SSLSocket) else "http"
        return f"{scheme}://{name}:{port}"

    def member_url(self, session: IssuedMemberSession) -> str:
        """Short-lived handoff a trusted sign-in adapter gives the browser.

        The secret stays in the URL fragment, which is not sent in the HTTP
        request, and the page immediately removes it from browser history.
        """
        return f"{self.base_url}/#session={session.bearer}"

    def invitation_url(self, proof: IssuedInvitationProof) -> str:
        """Out-of-band invitation link whose proof stays in the URL fragment."""
        return f"{self.base_url}/#invitation={proof.bearer}"

    def start(self) -> Self:
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
