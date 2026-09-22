"""Issuing and checking the tokens a Bridge authenticates with.

Binding a member to a machine issues a token for that pair, kept on the
Bridge; several members on one machine hold several tokens, which is how
their requests stay distinguishable. The pinned Host Bridge already worked
this way in outline, asking for a user sign-in when a machine was not bound
and exchanging it for that machine's own token
(`docs/PHASE_7_MIGRATION.md`, "Bridge access tokens").

Two rules shape everything here. The platform keeps a fingerprint and never a
secret, so its own store is not worth stealing. And the secret is verified
before anything is said about the token's state, so somebody who does not
hold it learns nothing: an unknown token and a wrong secret are the same
answer, and only the holder of a real secret is told that their token was
revoked, has expired, or belongs to a binding the platform has withdrawn.
"""

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Literal

from pydantic import TypeAdapter

from common.base import Symbol
from common.enrollment import BridgeExecutionSubject
from common.identity import (
    ACCESS_TOKEN_METHOD,
    AuthenticatedActor,
    BridgeAccessGrant,
    IssuedAccessToken,
)
from control_plane.enrollment import InMemoryEnrollmentRegistry

# A generated secret is 32 random bytes in URL-safe form. The minimum below
# is what a caller-supplied one must reach: the fingerprint comparison is
# sound only for a value nobody can guess, and a short one is a password
# wearing a token's name.
SECRET_BYTES = 32
MIN_SECRET_CHARS = 32
# How long an authentication holds before the Bridge presents its token again.
DEFAULT_SESSION = timedelta(hours=1)

AccessErrorCode = Literal[
    "actor_not_admitted",
    "token_forbidden",
    "duplicate_token",
    "weak_secret",
    "authentication_failed",
    "token_revoked",
    "token_expired",
    "binding_withdrawn",
    "token_missing",
]


class AccessError(Exception):
    def __init__(self, code: AccessErrorCode) -> None:
        self.code: AccessErrorCode = code
        super().__init__(code)


def fingerprint(secret: str) -> str:
    """What the platform keeps instead of the secret. A plain digest is
    enough here and would not be for a password: the secret is 32 random
    bytes, so there is nothing to guess and nothing for a slow hash to slow
    down."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class InMemoryAccessTokens:
    """Side-effect-free reference for issuing and checking access tokens."""

    def __init__(self, enrollment: InMemoryEnrollmentRegistry) -> None:
        self.enrollment = enrollment
        self._grants: dict[str, BridgeAccessGrant] = {}

    def _admitted(self, actor: str, bridge_id: str) -> bool:
        return self.enrollment.admit(BridgeExecutionSubject(actor=actor, bridge_id=bridge_id))

    def _permitted(self, requested_by: str, actor: str, bridge_id: str) -> None:
        """Who may act on a member's token for a device: that member, at the
        keyboard getting their own token, or somebody who may administer the
        device. The same rule the enrollment registry uses for a binding,
        because a token is what a binding justifies."""
        if requested_by == actor:
            return
        if not self.enrollment.may_administer(requested_by, bridge_id):
            raise AccessError("token_forbidden")

    def _usable(self, grant: BridgeAccessGrant, now: datetime) -> bool:
        return grant.status == "active" and not grant.expired_at(now)

    def issue(
        self,
        requested_by: Symbol,
        actor: Symbol,
        bridge_id: Symbol,
        *,
        issued_at: datetime,
        expires_at: datetime | None = None,
        secret: str | None = None,
    ) -> IssuedAccessToken:
        """Issue the token that binding this member to this machine justifies.

        A token cannot exist without a binding the platform still honours, so
        this refuses unless the member is admitted on that device right now,
        and unless the caller is that member or may administer the device.
        """
        requester = TypeAdapter(Symbol).validate_python(requested_by)
        who = TypeAdapter(Symbol).validate_python(actor)
        device = TypeAdapter(Symbol).validate_python(bridge_id)
        self._permitted(requester, who, device)
        if not self._admitted(who, device):
            raise AccessError("actor_not_admitted")
        if any(
            item.actor == who and item.bridge_id == device and self._usable(item, issued_at)
            for item in self._grants.values()
        ):
            # Only a token that still works stands in the way. One that has
            # expired is spent, and a pair may be given another.
            raise AccessError("duplicate_token")
        value = secret if secret is not None else secrets.token_urlsafe(SECRET_BYTES)
        if len(value) < MIN_SECRET_CHARS:
            raise AccessError("weak_secret")
        grant = BridgeAccessGrant(
            token_id=f"token-{secrets.token_hex(8)}",
            actor=who,
            bridge_id=device,
            fingerprint=fingerprint(value),
            issued_at=issued_at,
            expires_at=expires_at,
        )
        self._grants[grant.token_id] = grant
        return IssuedAccessToken(grant.model_copy(deep=True), value)

    def authenticate(
        self,
        token_id: Symbol,
        secret: str,
        *,
        now: datetime | None = None,
        session: timedelta = DEFAULT_SESSION,
    ) -> AuthenticatedActor:
        """Decide who a Bridge is acting for, or why it may not.

        The secret is checked first and an unknown token is checked against a
        fingerprint that matches nothing, so the answer and the work are the
        same either way: somebody who does not hold a secret cannot learn
        that a token exists.
        """
        moment = now if now is not None else datetime.now(UTC)
        # A token id that is not even the shape of one is simply not a token
        # anybody holds, and gets the same answer as one that does not exist:
        # refusing it differently would be a way to ask what exists.
        grant = self._grants.get(token_id) if isinstance(token_id, str) else None
        expected = grant.fingerprint if grant is not None else fingerprint("")
        if not hmac.compare_digest(expected, fingerprint(secret)) or grant is None:
            raise AccessError("authentication_failed")
        # Past this line the holder proved the secret, so they are told what
        # is actually wrong rather than being left to guess.
        if grant.status != "active":
            raise AccessError("token_revoked")
        if grant.expired_at(moment):
            raise AccessError("token_expired")
        if not self._admitted(grant.actor, grant.bridge_id):
            # A withdrawn binding, a disabled member and a disabled device are
            # one answer: the platform no longer lets this member use this
            # machine.
            raise AccessError("binding_withdrawn")
        ends = moment + session
        if grant.expires_at is not None and grant.expires_at < ends:
            # A session never outlives the token it came from.
            ends = grant.expires_at
        return AuthenticatedActor(
            actor=grant.actor,
            bridge_id=grant.bridge_id,
            method=ACCESS_TOKEN_METHOD,
            authenticated_at=moment,
            expires_at=ends,
        )

    def grant(self, token_id: Symbol) -> BridgeAccessGrant:
        key = TypeAdapter(Symbol).validate_python(token_id)
        item = self._grants.get(key)
        if item is None:
            raise AccessError("token_missing")
        return item.model_copy(deep=True)

    def grants_for(
        self, bridge_id: Symbol, *, now: datetime | None = None
    ) -> tuple[BridgeAccessGrant, ...]:
        """Which tokens a device can currently be used with, for an operator
        to look at. An expired one is spent and is not listed as if it were
        live. There is no secret in any of them."""
        key = TypeAdapter(Symbol).validate_python(bridge_id)
        moment = now if now is not None else datetime.now(UTC)
        return tuple(
            item.model_copy(deep=True)
            for item in sorted(self._grants.values(), key=lambda entry: entry.token_id)
            if item.bridge_id == key and self._usable(item, moment)
        )

    def revoke(self, requested_by: Symbol, token_id: Symbol) -> BridgeAccessGrant:
        """Take back one token. Its own member may, and so may somebody who
        administers the device it belongs to; nobody else."""
        requester = TypeAdapter(Symbol).validate_python(requested_by)
        key = TypeAdapter(Symbol).validate_python(token_id)
        item = self._grants.get(key)
        if item is None:
            raise AccessError("token_missing")
        self._permitted(requester, item.actor, item.bridge_id)
        revoked = BridgeAccessGrant.model_validate({**item.model_dump(), "status": "revoked"})
        self._grants[key] = revoked
        return revoked.model_copy(deep=True)

    def revoke_for(
        self, requested_by: Symbol, actor: Symbol, bridge_id: Symbol
    ) -> tuple[BridgeAccessGrant, ...]:
        """Take back the tokens a binding justified. Withdrawing the binding
        is what should make them stop working; this makes them stop being."""
        requester = TypeAdapter(Symbol).validate_python(requested_by)
        who = TypeAdapter(Symbol).validate_python(actor)
        device = TypeAdapter(Symbol).validate_python(bridge_id)
        self._permitted(requester, who, device)
        return tuple(
            self.revoke(requester, item.token_id)
            for item in sorted(self._grants.values(), key=lambda entry: entry.token_id)
            if item.actor == who and item.bridge_id == device and item.status == "active"
        )
