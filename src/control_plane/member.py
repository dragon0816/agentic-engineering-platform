"""Authenticated member selection service for the shared platform.

This is deliberately separate from the Bridge wire. A Bridge token proves a
machine/member binding for catalog and synchronization; it is never accepted
as a browser session. A trusted sign-in adapter may mint the short-lived
member session used here after it has produced an ``AuthenticatedActor``.
"""

from __future__ import annotations

import hmac
import secrets
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, Self

from pydantic import AwareDatetime, model_validator

from common.assets import RegistryContract
from common.authorization import DeviceAssetSelection
from common.base import Sha256, Symbol
from common.enrollment import BridgeExecutionSubject
from common.identity import ACCESS_TOKEN_METHOD, AuthenticatedActor
from common.member import (
    MemberCatalogEntry,
    MemberCatalogReply,
    MemberCatalogRequest,
    MemberRevokeRequest,
    MemberSelectionReply,
    MemberSelectRequest,
)
from control_plane.authorization import AuthorizationError, InMemoryAuthorizationRegistry
from control_plane.enrollment import InMemoryEnrollmentRegistry
from control_plane.identity import fingerprint

MIN_SESSION_SECRET_CHARS = 32

MemberErrorCode = Literal[
    "authentication_failed",
    "session_expired",
    "actor_mismatch",
    "actor_unknown",
    "actor_disabled",
    "actor_not_admitted",
    "asset_not_published",
    "asset_not_entitled",
    "kind_mismatch",
    "duplicate_selection",
    "selection_missing",
    "decision_in_future",
    "invalid_request",
]


class MemberError(Exception):
    def __init__(self, code: MemberErrorCode) -> None:
        self.code: MemberErrorCode = code
        super().__init__(code)


class MemberSessionGrant(RegistryContract):
    """Secret-free record of a browser session created after direct sign-in."""

    session_id: Symbol
    actor: Symbol
    method: Symbol
    fingerprint: Sha256
    issued_at: AwareDatetime
    expires_at: AwareDatetime
    status: Literal["active", "revoked"] = "active"

    @model_validator(mode="after")
    def ends_after_issue(self) -> Self:
        if self.expires_at <= self.issued_at:
            raise ValueError("a member session must expire after it is issued")
        return self


class IssuedMemberSession:
    """The one return value that carries the opaque session secret."""

    __slots__ = ("grant", "secret")

    def __init__(self, grant: MemberSessionGrant, secret: str) -> None:
        self.grant = grant
        self.secret = secret

    @property
    def bearer(self) -> str:
        return f"{self.grant.session_id}:{self.secret}"

    def __repr__(self) -> str:
        return f"IssuedMemberSession(session_id={self.grant.session_id!r}, secret=[redacted])"


class InMemoryMemberSessions:
    """Side-effect-free session reference used behind a trusted sign-in adapter."""

    def __init__(self) -> None:
        self._grants: dict[str, MemberSessionGrant] = {}

    def issue(
        self,
        identity: AuthenticatedActor,
        *,
        now: datetime | None = None,
        secret: str | None = None,
    ) -> IssuedMemberSession:
        who = AuthenticatedActor.model_validate(identity)
        moment = now if now is not None else datetime.now(UTC)
        if who.bridge_id is not None or who.method == ACCESS_TOKEN_METHOD:
            raise ValueError("Bridge authentication cannot become a member browser session")
        if not who.valid_at(moment):
            raise ValueError("only a current authentication can create a member session")
        value = secret if secret is not None else secrets.token_urlsafe(32)
        if len(value) < MIN_SESSION_SECRET_CHARS:
            raise ValueError("member session secret is too short")
        grant = MemberSessionGrant(
            session_id=f"member-{secrets.token_hex(8)}",
            actor=who.actor,
            method=who.method,
            fingerprint=fingerprint(value),
            issued_at=moment,
            expires_at=who.expires_at,
        )
        self._grants[grant.session_id] = grant
        return IssuedMemberSession(grant.model_copy(deep=True), value)

    def authenticate(
        self, session_id: str, secret: str, *, now: datetime | None = None
    ) -> AuthenticatedActor:
        moment = now if now is not None else datetime.now(UTC)
        grant = self._grants.get(session_id)
        expected = grant.fingerprint if grant is not None else fingerprint("")
        if grant is None or not hmac.compare_digest(expected, fingerprint(secret)):
            raise MemberError("authentication_failed")
        if grant.status != "active" or moment >= grant.expires_at:
            raise MemberError("session_expired")
        return AuthenticatedActor(
            actor=grant.actor,
            method=grant.method,
            authenticated_at=grant.issued_at,
            expires_at=grant.expires_at,
        )


_AUTHORIZATION_CODES: dict[str, MemberErrorCode] = {
    "session_expired": "session_expired",
    "actor_mismatch": "actor_mismatch",
    "actor_unknown": "actor_unknown",
    "actor_disabled": "actor_disabled",
    "actor_not_admitted": "actor_not_admitted",
    "asset_not_published": "asset_not_published",
    "asset_not_entitled": "asset_not_entitled",
    "kind_mismatch": "kind_mismatch",
    "duplicate_selection": "duplicate_selection",
    "selection_missing": "selection_missing",
    "decision_in_future": "decision_in_future",
}


class MemberService:
    """Member catalog and selection operations, independent of HTTP."""

    def __init__(
        self,
        *,
        enrollment: InMemoryEnrollmentRegistry,
        authorization: InMemoryAuthorizationRegistry,
        sessions: InMemoryMemberSessions,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self.enrollment = enrollment
        self.authorization = authorization
        self.sessions = sessions
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._lock = threading.Lock()

    def _who(self, session_id: str, secret: str, now: datetime) -> AuthenticatedActor:
        return self.sessions.authenticate(session_id, secret, now=now)

    def _admitted(self, who: AuthenticatedActor, bridge_id: str) -> None:
        if not self.enrollment.admit(BridgeExecutionSubject(actor=who.actor, bridge_id=bridge_id)):
            raise MemberError("actor_not_admitted")

    def catalog(
        self, session_id: str, secret: str, request: MemberCatalogRequest
    ) -> MemberCatalogReply:
        item = MemberCatalogRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            self._admitted(who, item.bridge_id)
            available = self.authorization.available(who, now=now)
            selected = {
                selection.asset.key
                for selection in self.authorization.authorization(
                    item.bridge_id, issued_at=now
                ).for_actor(who.actor)
                if selection.kind in ("workflow", "skill")
            }
            entries = tuple(
                MemberCatalogEntry(
                    package=package,
                    selected=package.metadata.identity.key in selected,
                )
                for package in available
            )
        return MemberCatalogReply(bridge_id=item.bridge_id, entries=entries)

    def select(
        self, session_id: str, secret: str, request: MemberSelectRequest
    ) -> MemberSelectionReply:
        item = MemberSelectRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            package = self.authorization.packages.get(item.asset)
            if package is None:
                raise MemberError("asset_not_published")
            if package.kind not in ("workflow", "skill"):
                raise MemberError("kind_mismatch")
            try:
                selected = self.authorization.select(
                    who,
                    DeviceAssetSelection(
                        bridge_id=item.bridge_id,
                        actor=who.actor,
                        kind=package.kind,
                        asset=item.asset,
                        decided_at=now,
                    ),
                    now=now,
                )
            except AuthorizationError as error:
                raise MemberError(_AUTHORIZATION_CODES.get(error.code, "invalid_request")) from None
        return MemberSelectionReply(selection=selected)

    def revoke(
        self, session_id: str, secret: str, request: MemberRevokeRequest
    ) -> MemberSelectionReply:
        item = MemberRevokeRequest.model_validate(request)
        now = self._clock()
        with self._lock:
            who = self._who(session_id, secret, now)
            self._admitted(who, item.bridge_id)
            try:
                revoked = self.authorization.revoke(who, item.bridge_id, item.asset, now=now)
            except AuthorizationError as error:
                raise MemberError(_AUTHORIZATION_CODES.get(error.code, "invalid_request")) from None
        return MemberSelectionReply(selection=revoked)
