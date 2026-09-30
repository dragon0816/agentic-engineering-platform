"""Invitation-only direct member sign-in for the shared platform.

The invitation metadata remains secret-free.  This adapter keeps a separate
fingerprint for the out-of-band proof, accepts it once, records the platform
member and hands the resulting direct identity to the existing short-lived
member-session broker.
"""

from __future__ import annotations

import hmac
import secrets
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal

from common.enrollment import Invitation
from common.identity import AuthenticatedActor, InvitationProofGrant, IssuedInvitationProof
from control_plane.enrollment import EnrollmentError, InMemoryEnrollmentRegistry
from control_plane.identity import fingerprint
from control_plane.member import InMemoryMemberSessions, IssuedMemberSession

INVITATION_PROOF_METHOD = "invitation-proof"
INVITATION_SECRET_BYTES = 32
MIN_INVITATION_SECRET_CHARS = 32
DEFAULT_MEMBER_SESSION = timedelta(hours=1)

InvitationSignInErrorCode = Literal[
    "authentication_failed",
    "invitation_expired",
    "invitation_used",
    "invitation_revoked",
    "invalid_request",
]


class InvitationSignInError(Exception):
    def __init__(self, code: InvitationSignInErrorCode) -> None:
        self.code: InvitationSignInErrorCode = code
        super().__init__(code)


class InMemoryInvitationSignIn:
    """Reference invitation issuer and one-time direct sign-in adapter."""

    def __init__(
        self,
        *,
        enrollment: InMemoryEnrollmentRegistry,
        sessions: InMemoryMemberSessions,
        clock: Callable[[], datetime] | None = None,
        session_ttl: timedelta = DEFAULT_MEMBER_SESSION,
    ) -> None:
        if session_ttl <= timedelta(0):
            raise ValueError("member session duration must be positive")
        self.enrollment = enrollment
        self.sessions = sessions
        self._clock = clock if clock is not None else lambda: datetime.now(UTC)
        self._session_ttl = session_ttl
        self._grants: dict[str, InvitationProofGrant] = {}
        self._lock = threading.Lock()

    def invite(
        self,
        invitation: Invitation,
        *,
        expires_at: datetime,
        secret: str | None = None,
    ) -> IssuedInvitationProof:
        """Issue invitation metadata and its separately delivered proof."""
        item = Invitation.model_validate(invitation).model_copy(deep=True)
        now = self._clock()
        value = secret if secret is not None else secrets.token_urlsafe(INVITATION_SECRET_BYTES)
        if len(value) < MIN_INVITATION_SECRET_CHARS:
            raise InvitationSignInError("invalid_request")
        grant = InvitationProofGrant(
            invitation_id=item.invitation_id,
            actor=item.actor,
            fingerprint=fingerprint(value),
            issued_at=now,
            expires_at=expires_at,
        )
        with self._lock:
            self.enrollment.issue(item)
            self._grants[grant.invitation_id] = grant
        return IssuedInvitationProof(grant.model_copy(deep=True), value)

    def accept(self, invitation_id: str, secret: str) -> IssuedMemberSession:
        """Redeem a proof once and create the existing short-lived member session."""
        now = self._clock()
        with self._lock:
            grant = self._grants.get(invitation_id)
            expected = grant.fingerprint if grant is not None else fingerprint("")
            if grant is None or not hmac.compare_digest(expected, fingerprint(secret)):
                raise InvitationSignInError("authentication_failed")
            if grant.status == "redeemed":
                raise InvitationSignInError("invitation_used")
            if grant.status == "revoked":
                raise InvitationSignInError("invitation_revoked")
            if now >= grant.expires_at:
                raise InvitationSignInError("invitation_expired")
            try:
                self.enrollment.accept(grant.invitation_id, grant.actor)
            except EnrollmentError as error:
                if error.code == "invitation_used":
                    raise InvitationSignInError("invitation_used") from None
                raise InvitationSignInError("invalid_request") from None
            expires_at = min(now + self._session_ttl, grant.expires_at)
            identity = AuthenticatedActor(
                actor=grant.actor,
                method=INVITATION_PROOF_METHOD,
                authenticated_at=now,
                expires_at=expires_at,
            )
            session = self.sessions.issue(identity, now=now)
            redeemed = InvitationProofGrant.model_validate(
                {**grant.model_dump(), "status": "redeemed"}
            )
            self._grants[grant.invitation_id] = redeemed
            return session

    def grant(self, invitation_id: str) -> InvitationProofGrant:
        item = self._grants.get(invitation_id)
        if item is None:
            raise InvitationSignInError("authentication_failed")
        return item.model_copy(deep=True)

    def revoke(self, invitation_id: str) -> InvitationProofGrant:
        with self._lock:
            item = self._grants.get(invitation_id)
            if item is None:
                raise InvitationSignInError("authentication_failed")
            if item.status != "active":
                raise InvitationSignInError("invitation_used")
            revoked = InvitationProofGrant.model_validate(
                {**item.model_dump(), "status": "revoked"}
            )
            self._grants[invitation_id] = revoked
            return revoked.model_copy(deep=True)
