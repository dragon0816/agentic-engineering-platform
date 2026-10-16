"""Standard-library HTTP entry point for authenticated platform members."""

from __future__ import annotations

import json
import secrets
import ssl
import threading
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import TracebackType
from typing import Any, Self

from pydantic import ValidationError

from common.base import Contract
from common.enrollment import Invitation
from common.identity import AuthenticatedActor, IssuedInvitationProof
from common.member import (
    AdminBridgeRequest,
    AdminInvitationCreateRequest,
    AdminInvitationListReply,
    AdminInvitationMetadata,
    AdminInvitationRevokeRequest,
    AdminMemberRequest,
    AdminMemberUpdateRequest,
    AdminPasswordResetRequest,
    AssetAccessListRequest,
    AssetAccessUpdateRequest,
    AssetApproveRequest,
    AssetCoEditorRequest,
    AssetDeprecateRequest,
    AssetManifestRequest,
    AssetNameRequest,
    AssetNextVersionRequest,
    AssetRejectRequest,
    AssetSubmissionListRequest,
    AssetSubmissionRequest,
    AssetSubmitRequest,
    AssetTransferRequest,
    BridgeEnrollRequest,
    MemberCatalogRequest,
    MemberReplaceRequest,
    MemberRevokeRequest,
    MemberSelectRequest,
)
from control_plane.enrollment import EnrollmentError
from control_plane.http import finish_tls, tls_listener
from control_plane.member import IssuedMemberSession, MemberError, MemberService
from control_plane.member_login import InMemoryMemberLogins
from control_plane.member_page import PAGE
from control_plane.member_password import (
    PASSWORD_METHOD,
    PROBLEM_MESSAGES,
    IssuedPasswordReset,
    MemberPasswords,
    PasswordError,
)
from control_plane.member_signin import (
    DEFAULT_MEMBER_SESSION,
    InMemoryInvitationSignIn,
    InvitationSignInError,
)
from control_plane.member_ticket import (
    TICKET_LOGIN_LABEL,
    TICKET_METHOD,
    BrowserTickets,
)
from control_plane.submissions import SubmissionError
from software.marketplace import ApplicationCatalogRequest

API_PREFIX = "/v1/member/"
MAX_BODY_BYTES = 256 * 1024
BEARER = "Bearer "
INVITATION = "Invitation "
LOGIN = "Login "
RESET = "Reset "
TICKET = "Ticket "

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
    "not_administrator": 403,
    "asset_deprecated": 409,
    "publisher_not_authorized": 403,
    "name_missing": 404,
    "not_name_owner": 403,
    "ownership_changed": 409,
    "co_editor_unknown": 400,
    "co_editor_exists": 409,
    "co_editor_missing": 404,
    "owner_unchanged": 409,
    "new_owner_unknown": 400,
    "version_missing": 404,
    "version_deprecated": 409,
    "access_member_unknown": 400,
    # Member publish with a review queue (owner 2026-10-15).
    "manifest_invalid": 400,
    "artifact_too_large": 413,
    "missing_dependency": 409,
    "submission_missing": 404,
    "submission_not_pending": 409,
    "self_review_refused": 403,
    "version_superseded": 409,
    # Bridge self-enrollment (owner 2026-10-15).
    "device_owner_mismatch": 403,
    "administrator_required": 403,
    "device_disabled": 409,
    "device_in_use": 409,
    "device_missing": 404,
    # Platform overview (owner 2026-10-15).
    "last_administrator": 409,
    # Account and password sign-in (owner 2026-10-15).
    "password_rejected": 400,
    "password_already_set": 409,
    "password_not_set": 409,
    "reset_link_used": 409,
    "reset_link_expired": 401,
    "reset_link_revoked": 401,
    # One-click sign-in from Agent Web (owner 2026-10-15).
    "ticket_used": 409,
    "ticket_expired": 401,
}
# The label of a login a member issues for their Personal Agent, so the
# portal and an audit can tell it from the browser's own.
AGENT_LOGIN_LABEL = "Personal Agent"
BROWSER_LOGIN_LABEL = "Marketplace browser"


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


def _login_credential(header: str | None) -> tuple[str, str] | None:
    if header is None or not header.startswith(LOGIN):
        return None
    login_id, separator, secret = header[len(LOGIN) :].strip().partition(":")
    if not separator or not login_id or not secret:
        return None
    return login_id, secret


def _reset_credential(header: str | None) -> tuple[str, str] | None:
    if header is None or not header.startswith(RESET):
        return None
    reset_id, separator, secret = header[len(RESET) :].strip().partition(":")
    if not separator or not reset_id or not secret:
        return None
    return reset_id, secret


def _ticket_credential(header: str | None) -> tuple[str, str] | None:
    if header is None or not header.startswith(TICKET):
        return None
    ticket_id, separator, secret = header[len(TICKET) :].strip().partition(":")
    if not separator or not ticket_id or not secret:
        return None
    return ticket_id, secret


def _strings(raw: object, *names: str) -> tuple[str, ...]:
    """Exactly these string fields. A body carrying a password is parsed
    here, not as a contract, and the error says nothing about the values."""
    if (
        not isinstance(raw, dict)
        or set(raw) != set(names)
        or not all(isinstance(raw[name], str) for name in names)
    ):
        raise ValueError("invalid password request")
    return tuple(str(raw[name]) for name in names)


def _password_refusal(error: PasswordError) -> dict[str, str]:
    if error.code == "password_rejected" and error.reason is not None:
        return {
            "code": error.code,
            "reason": error.reason,
            "message": PROBLEM_MESSAGES[error.reason],
        }
    return {"code": error.code}


# Why a name was refused, in words the portal shows as they are (owner,
# 2026-10-15: an invitation for "name@example" failed with only
# `invalid_request`). Account and group names are `common.base.Symbol`.
NAME_RULE = (
    "letters, digits, '.', '-' and '_' only, starting with a letter or '_'; no '@' or spaces"
)
_NAME_REASONS = {
    "actor": ("account_invalid", f"Account names use {NAME_RULE}, for example leo.chi."),
    "groups": ("group_invalid", f"Group names use {NAME_RULE}, for example engineering."),
    "members": ("account_invalid", f"Account names use {NAME_RULE}, for example leo.chi."),
    "co_editor": ("account_invalid", f"Account names use {NAME_RULE}, for example leo.chi."),
}


def _invalid(error: ValidationError) -> dict[str, str]:
    """`invalid_request`, with the reason when a name was what was wrong. The
    submitted value is never echoed."""
    for detail in error.errors():
        location = detail.get("loc", ())
        field = location[0] if location else None
        # A field the request may not carry at all is not a badly written name.
        if detail.get("type") == "extra_forbidden":
            continue
        if isinstance(field, str) and field in _NAME_REASONS:
            reason, message = _NAME_REASONS[field]
            return {"code": "invalid_request", "reason": reason, "message": message}
    return {"code": "invalid_request"}


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
        if operation not in (
            "sign-in",
            "session",
            "me",
            "catalog",
            "applications",
            "select",
            "replace",
            "revoke",
            "admin/invitations",
            "admin/invitations/list",
            "admin/invitations/revoke",
            "admin/extensions",
            "assets/ownership",
            "assets/next-version",
            "assets/co-editors/add",
            "assets/co-editors/remove",
            "assets/transfer",
            "assets/deprecate",
            "assets/access",
            "assets/access/update",
            "assets/submit",
            "assets/submissions",
            "assets/submissions/withdraw",
            "admin/submissions/list",
            "admin/submissions/get",
            "admin/submissions/approve",
            "admin/submissions/reject",
            "logins/issue-agent",
            "bridges/enroll",
            "admin/bridges/list",
            "admin/bridges/disable",
            "admin/overview",
            "admin/members/update",
            "assets/manifest",
            "sign-in/check",
            "sign-in/password",
            "password/reset",
            "password/status",
            "password/set",
            "password/change",
            "admin/members/password-reset",
            "admin/members/sign-out",
            "admin/members/credentials",
            "browser-ticket",
            "sign-in/ticket",
        ):
            self._json(404, {"code": "invalid_request"})
            return
        if operation == "sign-in":
            self._sign_in()
            return
        if operation == "session":
            self._refresh_session()
            return
        if operation in ("sign-in/check", "sign-in/password", "password/reset", "sign-in/ticket"):
            self._password_entry(operation)
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
            if operation == "me":
                reply = self.server.service.identity(*credential)
            elif operation == "catalog":
                reply = self.server.service.catalog(
                    *credential, MemberCatalogRequest.model_validate(raw)
                )
            elif operation == "applications":
                reply = self.server.service.application_catalog(
                    *credential, ApplicationCatalogRequest.model_validate(raw)
                )
            elif operation == "admin/extensions":
                if raw != {}:
                    raise ValueError("extension catalog accepts no request fields")
                reply = self.server.service.extension_catalog(*credential)
            elif operation == "select":
                reply = self.server.service.select(
                    *credential, MemberSelectRequest.model_validate(raw)
                )
            elif operation == "replace":
                reply = self.server.service.replace(
                    *credential, MemberReplaceRequest.model_validate(raw)
                )
            elif operation == "revoke":
                reply = self.server.service.revoke(
                    *credential, MemberRevokeRequest.model_validate(raw)
                )
            elif operation == "assets/ownership":
                reply = self.server.service.asset_ownership(
                    *credential, AssetNameRequest.model_validate(raw)
                )
            elif operation == "assets/next-version":
                reply = self.server.service.asset_next_version(
                    *credential, AssetNextVersionRequest.model_validate(raw)
                )
            elif operation == "assets/co-editors/add":
                reply = self.server.service.asset_add_co_editor(
                    *credential, AssetCoEditorRequest.model_validate(raw)
                )
            elif operation == "assets/co-editors/remove":
                reply = self.server.service.asset_remove_co_editor(
                    *credential, AssetCoEditorRequest.model_validate(raw)
                )
            elif operation == "assets/transfer":
                reply = self.server.service.asset_transfer(
                    *credential, AssetTransferRequest.model_validate(raw)
                )
            elif operation == "assets/deprecate":
                reply = self.server.service.asset_deprecate(
                    *credential, AssetDeprecateRequest.model_validate(raw)
                )
            elif operation == "assets/access":
                reply = self.server.service.asset_access(
                    *credential, AssetAccessListRequest.model_validate(raw)
                )
            elif operation == "assets/access/update":
                reply = self.server.service.asset_access_update(
                    *credential, AssetAccessUpdateRequest.model_validate(raw)
                )
            elif operation == "assets/submit":
                reply = self.server.service.asset_submit(
                    *credential, AssetSubmitRequest.model_validate(raw)
                )
            elif operation == "assets/submissions":
                if raw != {}:
                    raise ValueError("the member's submissions take no request fields")
                reply = self.server.service.asset_submissions(*credential)
            elif operation == "assets/submissions/withdraw":
                reply = self.server.service.asset_withdraw(
                    *credential, AssetSubmissionRequest.model_validate(raw)
                )
            elif operation == "admin/submissions/list":
                reply = self.server.service.review_queue(
                    *credential, AssetSubmissionListRequest.model_validate(raw)
                )
            elif operation == "admin/submissions/get":
                reply = self.server.service.review_detail(
                    *credential, AssetSubmissionRequest.model_validate(raw)
                )
            elif operation == "admin/submissions/approve":
                reply = self.server.service.review_approve(
                    *credential, AssetApproveRequest.model_validate(raw)
                )
            elif operation == "admin/submissions/reject":
                reply = self.server.service.review_reject(
                    *credential, AssetRejectRequest.model_validate(raw)
                )
            elif operation == "logins/issue-agent":
                # A login the member hands to their own Personal Agent, shown
                # once; the Agent trades it for short sessions to publish.
                if raw != {}:
                    raise ValueError("an Agent login takes no request fields")
                member = self.server.service.identity(*credential)
                login = self.server.logins.issue(
                    member.actor, label=AGENT_LOGIN_LABEL, now=self.server.service.now()
                )
                self._json(
                    200,
                    {
                        "login": login.bearer,
                        "login_id": login.grant.login_id,
                        "expires_at": login.grant.expires_at.isoformat(),
                    },
                )
                return
            elif operation == "bridges/enroll":
                # The member's own Agent enrolls this computer. The Bridge
                # token is in this reply once and nowhere else.
                issued = self.server.service.enroll_bridge(
                    *credential, BridgeEnrollRequest.model_validate(raw)
                )
                expires = issued.grant.expires_at
                self._json(
                    200,
                    {
                        "bridge_id": issued.grant.bridge_id,
                        "token_id": issued.grant.token_id,
                        "secret": issued.secret,
                        "issued_at": issued.grant.issued_at.isoformat(),
                        "expires_at": expires.isoformat() if expires is not None else None,
                    },
                )
                return
            elif operation == "admin/bridges/list":
                if raw != {}:
                    raise ValueError("the Bridge list takes no request fields")
                reply = self.server.service.bridges(*credential)
            elif operation == "admin/bridges/disable":
                reply = self.server.service.disable_bridge(
                    *credential, AdminBridgeRequest.model_validate(raw)
                )
            elif operation == "admin/overview":
                # Everything on the platform for an administrator, read-only
                # and without any secret (owner 2026-10-15).
                if raw != {}:
                    raise ValueError("the overview takes no request fields")
                sign_in = self.server.sign_in
                expiry = (
                    {grant.invitation_id: grant.expires_at for grant in sign_in.grants()}
                    if sign_in is not None
                    else {}
                )
                reply = self.server.service.overview(*credential, invitation_expiry=expiry)
            elif operation == "assets/manifest":
                reply = self.server.service.asset_manifest(
                    *credential, AssetManifestRequest.model_validate(raw)
                )
            elif operation == "admin/members/update":
                reply = self.server.service.update_member(
                    *credential, AdminMemberUpdateRequest.model_validate(raw)
                )
            elif operation == "browser-ticket":
                # One-click sign-in from Agent Web (owner 2026-10-15): the
                # member's Agent, with its session, gets a single-use ticket
                # good for 60 seconds that the browser trades for a sign-in.
                if raw != {}:
                    raise ValueError("a browser ticket takes no request fields")
                member = self.server.service.identity(*credential)
                if not self._active(member.actor):
                    raise MemberError("actor_disabled")
                ticket = self.server.tickets.issue(member.actor, now=self.server.service.now())
                self._json(
                    200,
                    {
                        "ticket": ticket.bearer,
                        "expires_at": ticket.grant.expires_at.isoformat(),
                    },
                )
                return
            elif operation == "password/status":
                if raw != {}:
                    raise ValueError("the password status takes no request fields")
                member = self.server.service.identity(*credential)
                record = self.server.passwords.record(member.actor)
                self._json(
                    200,
                    {
                        "password_set": record is not None,
                        "set_at": record.set_at.isoformat() if record is not None else None,
                    },
                )
                return
            elif operation == "password/set":
                (password,) = _strings(raw, "password")
                member = self.server.service.identity(*credential)
                self.server.passwords.set_first(
                    member.actor, password, now=self.server.service.now()
                )
                self._json(200, {"password_set": True})
                return
            elif operation == "password/change":
                current, new = _strings(raw, "current_password", "new_password")
                member = self.server.service.identity(*credential)
                if not self.server.passwords.has_password(member.actor):
                    raise PasswordError("password_not_set")
                now = self.server.service.now()
                self.server.passwords.authenticate(
                    member.actor,
                    current,
                    address=self.client_address[0],
                    now=now,
                    active=self._active,
                )
                self.server.passwords.set(member.actor, new, now=now, set_by="change")
                # The other browsers are signed out; this one gets a new login.
                self._sign_out(member.actor, keep_label=AGENT_LOGIN_LABEL)
                self._signed_in(member.actor)
                return
            elif operation == "admin/members/password-reset":
                reset_request = AdminPasswordResetRequest.model_validate(raw)
                who = self.server.service.administrator(*credential)
                self._member(reset_request.actor)
                reset_link = self.server.passwords.issue_reset(
                    reset_request.actor,
                    issued_by=who.actor,
                    now=self.server.service.now(),
                    minutes=reset_request.valid_for_minutes,
                )
                self._json(
                    200,
                    {
                        "actor": reset_link.grant.actor,
                        "reset_id": reset_link.grant.reset_id,
                        "expires_at": reset_link.grant.expires_at.isoformat(),
                        "url": self.server.reset_url(reset_link),
                    },
                )
                return
            elif operation == "admin/members/sign-out":
                member_request = AdminMemberRequest.model_validate(raw)
                self.server.service.administrator(*credential)
                self._member(member_request.actor)
                logins, sessions = self._sign_out(member_request.actor, keep_label=None)
                self._json(
                    200,
                    {
                        "actor": member_request.actor,
                        "logins_revoked": logins,
                        "sessions_revoked": sessions,
                    },
                )
                return
            elif operation == "admin/members/credentials":
                if raw != {}:
                    raise ValueError("the credential overview takes no request fields")
                self.server.service.administrator(*credential)
                now = self.server.service.now()
                rows = []
                for user in self.server.service.enrollment.users():
                    record = self.server.passwords.record(user.actor)
                    pending = self.server.passwords.pending_reset(user.actor, now)
                    rows.append(
                        {
                            "actor": user.actor,
                            "status": user.status,
                            "password_set": record is not None,
                            "password_set_at": (
                                record.set_at.isoformat() if record is not None else None
                            ),
                            "active_logins": len(self.server.logins.active(user.actor, now=now)),
                            "reset_link_expires_at": (
                                pending.expires_at.isoformat() if pending is not None else None
                            ),
                        }
                    )
                self._json(200, {"members": rows})
                return
            elif operation == "admin/invitations":
                create = AdminInvitationCreateRequest.model_validate(raw)
                who = self.server.service.administrator(*credential)
                sign_in = self.server.sign_in
                if sign_in is None:
                    raise MemberError("invalid_request")
                proof = sign_in.invite(
                    Invitation(
                        invitation_id=f"invite-{secrets.token_hex(8)}",
                        actor=create.actor,
                        issued_by=who.actor,
                        groups=create.groups,
                        role=create.role,
                    ),
                    expires_at=self.server.service.now()
                    + timedelta(minutes=create.valid_for_minutes),
                )
                metadata = AdminInvitationMetadata(
                    invitation=self.server.service.enrollment.invitation(proof.grant.invitation_id),
                    expires_at=proof.grant.expires_at,
                )
                self._json(
                    200,
                    {
                        "invitation": metadata.model_dump(mode="json"),
                        "url": self.server.invitation_url(proof),
                    },
                )
                return
            elif operation == "admin/invitations/list":
                self.server.service.administrator(*credential)
                sign_in = self.server.sign_in
                if sign_in is None:
                    raise MemberError("invalid_request")
                grants = {grant.invitation_id: grant for grant in sign_in.grants()}
                reply = AdminInvitationListReply(
                    invitations=tuple(
                        AdminInvitationMetadata(
                            invitation=invitation,
                            expires_at=grants[invitation.invitation_id].expires_at,
                        )
                        for invitation in self.server.service.enrollment.invitations()
                        if invitation.invitation_id in grants
                    )
                )
            else:
                revoke_request = AdminInvitationRevokeRequest.model_validate(raw)
                who = self.server.service.administrator(*credential)
                sign_in = self.server.sign_in
                if sign_in is None:
                    raise MemberError("invalid_request")
                invitation = self.server.service.enrollment.revoke_invitation(
                    who.actor, revoke_request.invitation_id
                )
                sign_in.revoke(revoke_request.invitation_id)
                self._json(200, {"invitation": invitation.model_dump(mode="json")})
                return
        except ValidationError as error:
            self._json(400, _invalid(error))
            return
        except ValueError:
            self._json(400, {"code": "invalid_request"})
            return
        except PasswordError as error:
            self._json(STATUS_FOR[error.code], _password_refusal(error))
            return
        except (MemberError, SubmissionError) as error:
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
        if length < 0 or length > MAX_BODY_BYTES:
            self._json(400, {"code": "invalid_request"})
            return
        try:
            # Empty: the invitation alone signs in (automation, and members
            # who set a password later). With `{"password"}` the password is
            # checked against the policy before the invitation is used up,
            # and set in the same step (owner 2026-10-15).
            password: str | None = None
            if length:
                (password,) = _strings(json.loads(self.rfile.read(length)), "password")
            if password is not None:
                grant = self.server.sign_in.check(*credential)
                self.server.passwords.check_policy(grant.actor, password)
            session = self.server.sign_in.accept(*credential)
            if password is not None:
                self.server.passwords.set(
                    session.grant.actor,
                    password,
                    now=self.server.service.now(),
                    set_by="invitation",
                )
            login = self.server.logins.issue(
                session.grant.actor,
                label=BROWSER_LOGIN_LABEL,
                now=self.server.service.now(),
            )
        except InvitationSignInError as error:
            self._json(STATUS_FOR[error.code], {"code": error.code})
            return
        except PasswordError as error:
            self._json(STATUS_FOR[error.code], _password_refusal(error))
            return
        except ValueError:
            self._json(400, {"code": "invalid_request"})
            return
        except Exception:  # noqa: BLE001 - no traceback crosses the sign-in boundary
            self._json(500, {"code": "internal_error"})
            return
        self._json(
            200,
            {
                "session": session.bearer,
                "login": login.bearer,
                "expires_at": session.grant.expires_at.isoformat(),
            },
        )

    def _refresh_session(self) -> None:
        credential = _login_credential(self.headers.get("Authorization"))
        if credential is None:
            self._json(401, {"code": "authentication_failed"})
            return
        try:
            identity = self.server.logins.authenticate(*credential, now=self.server.service.now())
            # A disabled member's stored login no longer signs them in.
            if not self._active(identity.actor):
                raise MemberError("actor_disabled")
            session = self.server.service.sessions.issue(identity, now=self.server.service.now())
        except MemberError as error:
            self._json(STATUS_FOR[error.code], {"code": error.code})
            return
        except Exception:  # noqa: BLE001
            self._json(500, {"code": "internal_error"})
            return
        self._json(
            200,
            {"session": session.bearer, "expires_at": session.grant.expires_at.isoformat()},
        )

    # -- Account and password sign-in (owner 2026-10-15) -------------------

    def _active(self, actor: str) -> bool:
        try:
            return self.server.service.enrollment.user(actor).status == "active"
        except (EnrollmentError, ValueError):
            return False

    def _member(self, actor: str) -> None:
        try:
            self.server.service.enrollment.user(actor)
        except EnrollmentError:
            raise MemberError("actor_unknown") from None

    def _sign_out(self, actor: str, *, keep_label: str | None) -> tuple[int, int]:
        logins = self.server.logins.revoke_actor(actor, keep_label=keep_label)
        sessions = self.server.service.sessions.revoke_actor(actor)
        return logins, sessions

    def _signed_in(
        self, actor: str, *, method: str = PASSWORD_METHOD, label: str = BROWSER_LOGIN_LABEL
    ) -> None:
        """The same browser login and one-hour session an invitation gives."""
        now = self.server.service.now()
        identity = AuthenticatedActor(
            actor=actor,
            method=method,
            authenticated_at=now,
            expires_at=now + DEFAULT_MEMBER_SESSION,
        )
        session = self.server.service.sessions.issue(identity, now=now)
        login = self.server.logins.issue(actor, label=label, now=now)
        self._json(
            200,
            {
                "session": session.bearer,
                "login": login.bearer,
                "expires_at": session.grant.expires_at.isoformat(),
            },
        )

    def _password_entry(self, operation: str) -> None:
        """Routes used before anyone is signed in: account and password,
        a password reset link, and checking an invitation or reset link."""
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
        header = self.headers.get("Authorization")
        passwords = self.server.passwords
        try:
            raw: object = json.loads(self.rfile.read(length)) if length else {}
            now = self.server.service.now()
            if operation == "sign-in/password":
                account, password = _strings(raw, "account", "password")
                actor = passwords.authenticate(
                    account,
                    password,
                    address=self.client_address[0],
                    now=now,
                    active=self._active,
                )
                self._signed_in(actor)
            elif operation == "sign-in/ticket":
                ticket = _ticket_credential(header)
                if ticket is None:
                    raise MemberError("authentication_failed")
                if raw != {}:
                    raise ValueError("a ticket sign-in takes no request fields")
                actor = self.server.tickets.redeem(*ticket, now=now)
                if not self._active(actor):
                    raise MemberError("actor_disabled")
                # One Agent Web browser login per member: the earlier one ends.
                for earlier in self.server.logins.active(actor, now=now):
                    if earlier.label == TICKET_LOGIN_LABEL:
                        self.server.logins.revoke(earlier.login_id)
                self._signed_in(actor, method=TICKET_METHOD, label=TICKET_LOGIN_LABEL)
            elif operation == "password/reset":
                reset = _reset_credential(header)
                if reset is None:
                    raise PasswordError("authentication_failed")
                (password,) = _strings(raw, "password")
                actor = passwords.redeem_reset(*reset, password, now=now, active=self._active)
                # Forgot password: every browser of this member is signed out.
                self._sign_out(actor, keep_label=AGENT_LOGIN_LABEL)
                self._signed_in(actor)
            else:
                if raw != {}:
                    raise ValueError("a link check takes no request fields")
                invitation = _invitation_credential(header)
                reset = _reset_credential(header)
                if invitation is not None and self.server.sign_in is not None:
                    grant = self.server.sign_in.check(*invitation)
                    purpose, actor, expires_at = "invitation", grant.actor, grant.expires_at
                elif reset is not None:
                    reset_grant = passwords.check_reset(*reset, now=now)
                    purpose, actor = "reset", reset_grant.actor
                    expires_at = reset_grant.expires_at
                else:
                    raise PasswordError("authentication_failed")
                self._json(
                    200,
                    {
                        "purpose": purpose,
                        "actor": actor,
                        "expires_at": expires_at.isoformat(),
                        "password_set": passwords.has_password(actor),
                    },
                )
        except PasswordError as error:
            self._json(STATUS_FOR[error.code], _password_refusal(error))
        except InvitationSignInError as error:
            self._json(STATUS_FOR[error.code], {"code": error.code})
        except MemberError as error:
            self._json(STATUS_FOR[error.code], {"code": error.code})
        except ValueError:
            self._json(400, {"code": "invalid_request"})
        except Exception:  # noqa: BLE001 - no traceback crosses the sign-in boundary
            self._json(500, {"code": "internal_error"})


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
        logins: InMemoryMemberLogins | None = None,
        passwords: MemberPasswords | None = None,
        tickets: BrowserTickets | None = None,
    ) -> None:
        if ssl_context is None and host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("a member portal exposed beyond loopback requires TLS")
        self.service = service
        self.sign_in = sign_in
        self.logins = logins if logins is not None else InMemoryMemberLogins()
        self.passwords = passwords if passwords is not None else MemberPasswords()
        # Browser sign-in tickets live a minute, in memory only.
        self.tickets = tickets if tickets is not None else BrowserTickets()
        super().__init__((host, port), _Handler)
        if ssl_context is not None:
            # The handshake runs on each request's thread (control_plane.http).
            self.socket = tls_listener(ssl_context, self.socket)
        self._thread: threading.Thread | None = None

    def finish_request(self, request: Any, client_address: Any) -> None:
        if finish_tls(request):
            super().finish_request(request, client_address)

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

    def reset_url(self, issued: IssuedPasswordReset) -> str:
        """Out-of-band password reset link whose secret stays in the fragment."""
        return f"{self.base_url}/#reset={issued.bearer}"

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
