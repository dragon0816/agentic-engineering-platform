"""Revocable browser-login credentials that mint short member sessions."""

from __future__ import annotations

import hmac
import secrets
from datetime import UTC, datetime, timedelta

from common.identity import AuthenticatedActor, IssuedMemberLogin, MemberLoginGrant
from control_plane.identity import fingerprint
from control_plane.identity_store import SqliteIdentityStorage
from control_plane.member import MemberError

LOGIN_METHOD = "browser-login"
DEFAULT_LOGIN_TTL = timedelta(days=30)
DEFAULT_IDENTITY_TTL = timedelta(hours=1)
MIN_LOGIN_SECRET_CHARS = 32


class InMemoryMemberLogins:
    """Reference browser-login registry, optionally persisted in SQLite."""

    def __init__(self, *, storage: SqliteIdentityStorage | None = None) -> None:
        self._storage = storage
        self._grants = {
            item.login_id: item
            for item in (
                MemberLoginGrant.model_validate_json(raw)
                for raw in (() if storage is None else storage.records("identity_member_logins"))
            )
        }

    def _save(self, grant: MemberLoginGrant) -> None:
        if self._storage is not None:
            self._storage.put("identity_member_logins", grant.login_id, grant)

    def issue(
        self,
        actor: str,
        *,
        label: str,
        now: datetime | None = None,
        expires_at: datetime | None = None,
        secret: str | None = None,
    ) -> IssuedMemberLogin:
        moment = now if now is not None else datetime.now(UTC)
        value = secret if secret is not None else secrets.token_urlsafe(32)
        if len(value) < MIN_LOGIN_SECRET_CHARS:
            raise ValueError("browser login secret is too short")
        grant = MemberLoginGrant(
            login_id=f"login-{secrets.token_hex(8)}",
            actor=actor,
            fingerprint=fingerprint(value),
            label=label,
            issued_at=moment,
            expires_at=expires_at or moment + DEFAULT_LOGIN_TTL,
        )
        self._grants[grant.login_id] = grant
        self._save(grant)
        return IssuedMemberLogin(grant.model_copy(deep=True), value)

    def authenticate(
        self, login_id: str, secret: str, *, now: datetime | None = None
    ) -> AuthenticatedActor:
        moment = now if now is not None else datetime.now(UTC)
        grant = self._grants.get(login_id)
        expected = grant.fingerprint if grant is not None else fingerprint("")
        if grant is None or not hmac.compare_digest(expected, fingerprint(secret)):
            raise MemberError("authentication_failed")
        if grant.status != "active" or moment >= grant.expires_at:
            raise MemberError("session_expired")
        return AuthenticatedActor(
            actor=grant.actor,
            method=LOGIN_METHOD,
            authenticated_at=moment,
            expires_at=min(moment + DEFAULT_IDENTITY_TTL, grant.expires_at),
        )

    def revoke(self, login_id: str) -> MemberLoginGrant:
        grant = self._grants.get(login_id)
        if grant is None:
            raise MemberError("authentication_failed")
        revoked = MemberLoginGrant.model_validate({**grant.model_dump(), "status": "revoked"})
        self._grants[login_id] = revoked
        self._save(revoked)
        return revoked.model_copy(deep=True)
