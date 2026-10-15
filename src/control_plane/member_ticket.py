"""One-click sign-in from Agent Web to the Member Portal (owner 2026-10-15).

`docs/phases/PLATFORM_OVERVIEW.md` "One-click sign-in from Agent Web". A
member's Personal Agent, holding a member session, asks the portal for a
browser sign-in ticket: single use, valid for at most 60 seconds and bound to
that member. Agent Web opens `<portal>/#ticket=<id:secret>`; the portal page
redeems the ticket for the same browser login and session a password sign-in
gives, and removes the fragment from history at once.

Only a SHA-256 fingerprint of each 32-byte random secret is kept, and only in
memory: a ticket outlives no restart, which is fine for something that lives a
minute. The Personal Agent's own login never leaves the Agent.
"""

from __future__ import annotations

import hmac
import secrets
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timedelta

from control_plane.identity import fingerprint
from control_plane.member import MemberError

TICKET_METHOD = "agent-ticket"
TICKET_TTL = timedelta(seconds=60)
TICKET_SECRET_BYTES = 32
# Open tickets one member may hold at once; older ones are dropped first.
MAX_OPEN_PER_ACTOR = 5
# The label of the browser login a ticket gives. A new one replaces the
# member's earlier one, so opening the portal from Agent Web again and again
# does not pile up thirty-day logins.
TICKET_LOGIN_LABEL = "Agent Web sign-in"


@dataclass(frozen=True, slots=True)
class BrowserTicketGrant:
    ticket_id: str
    actor: str
    fingerprint: str
    issued_at: datetime
    expires_at: datetime
    used: bool = False


@dataclass(frozen=True, slots=True)
class IssuedBrowserTicket:
    grant: BrowserTicketGrant
    secret: str

    @property
    def bearer(self) -> str:
        return f"{self.grant.ticket_id}:{self.secret}"

    def __repr__(self) -> str:  # never show the secret
        return f"IssuedBrowserTicket(ticket_id={self.grant.ticket_id!r})"


class BrowserTickets:
    """Single-use, short-lived browser sign-in tickets, stored hashed."""

    def __init__(self, *, ttl: timedelta = TICKET_TTL) -> None:
        if not timedelta(0) < ttl <= TICKET_TTL:
            raise ValueError("a browser ticket lives more than zero and at most 60 seconds")
        self._ttl = ttl
        self._grants: dict[str, BrowserTicketGrant] = {}
        self._lock = threading.Lock()

    def _prune(self, now: datetime) -> None:
        for ticket_id, grant in list(self._grants.items()):
            if grant.used or now >= grant.expires_at:
                del self._grants[ticket_id]

    def issue(self, actor: str, *, now: datetime) -> IssuedBrowserTicket:
        secret = secrets.token_urlsafe(TICKET_SECRET_BYTES)
        grant = BrowserTicketGrant(
            ticket_id=f"ticket-{secrets.token_hex(8)}",
            actor=actor,
            fingerprint=fingerprint(secret),
            issued_at=now,
            expires_at=now + self._ttl,
        )
        with self._lock:
            self._prune(now)
            mine = sorted(
                (item for item in self._grants.values() if item.actor == actor),
                key=lambda item: item.issued_at,
            )
            for old in mine[: max(0, len(mine) - MAX_OPEN_PER_ACTOR + 1)]:
                del self._grants[old.ticket_id]
            self._grants[grant.ticket_id] = grant
        return IssuedBrowserTicket(grant, secret)

    def redeem(self, ticket_id: str, secret: str, *, now: datetime) -> str:
        """The member a ticket names, using it up. Unknown or wrong:
        `authentication_failed`; already used: `ticket_used`; too old:
        `ticket_expired`."""
        with self._lock:
            grant = self._grants.get(ticket_id)
            expected = grant.fingerprint if grant is not None else fingerprint("")
            if grant is None or not hmac.compare_digest(expected, fingerprint(secret)):
                raise MemberError("authentication_failed")
            if grant.used:
                raise MemberError("ticket_used")
            # Used up whatever happens next: a ticket is tried once.
            self._grants[ticket_id] = replace(grant, used=True)
            if now >= grant.expires_at:
                raise MemberError("ticket_expired")
            return grant.actor

    def grants(self) -> tuple[BrowserTicketGrant, ...]:
        """What is held, for tests and audits: fingerprints, never secrets."""
        with self._lock:
            return tuple(self._grants.values())
