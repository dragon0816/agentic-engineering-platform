"""Which teams the person on this PC belongs to (owner 2026-10-19).

Used for one thing only: whether a revision of a team-owned Workflow keeps the
Workflow's name on this PC (1.0.0 -> 1.0.1) or forks to `<name>-<actor>`
(`docs/phases/WORKFLOW_REVISION.md`). It grants nothing else: installing is
still the person's press, and publishing back to the Shared Platform is checked
by the platform against its own member records.

The source, in this order:

1. The Shared Platform, when this PC can reach its Member Portal with the
   Personal Agent login (host.json `publishing`): `POST /v1/member/me` answers
   the signed-in member's own groups. The answer is cached in the workspace
   with a timestamp, and the cache is used while the platform cannot be
   reached. The platform answers only for this PC's own account
   (`device.registered_by`); another actor gets no teams from it.
2. Otherwise, "Teams I belong to on this PC" from Agent Web Settings, a local
   declaration kept in the workspace (never in host.json). A revision made on
   it says so on the install card.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import Field, ValidationError, field_validator

from common.base import Contract, Symbol
from host_runtime.workspace import write_atomically

MembershipSource = Literal["platform", "platform_cache", "declared", "none"]
MAX_DECLARED_TEAMS = 20
#: A live platform answer is reused this long before asking again.
LIVE_REUSE_SECONDS = 300.0
#: Codes that mean the platform could not be reached; the cache answers.
OFFLINE_CODES = frozenset(
    {"platform_unreachable", "certificate_untrusted", "bad_reply", "request_failed"}
)
#: Codes that mean this PC has no platform connection at all; the declaration answers.
UNCONNECTED_CODES = frozenset({"login_missing", "publishing_not_configured"})

SETTINGS_FILE = "team-membership.json"
CACHE_FILE = "team-membership-cache.json"


class TeamDeclaration(Contract):
    """What the person declared in Agent Web Settings."""

    declared_teams: tuple[Symbol, ...] = Field(default=(), max_length=MAX_DECLARED_TEAMS)

    @field_validator("declared_teams")
    @classmethod
    def _unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(dict.fromkeys(value))


class TeamMembership(Contract):
    """The teams an actor belongs to and where that came from."""

    teams: tuple[Symbol, ...] = ()
    source: MembershipSource = "none"
    account: Symbol | None = None
    checked_at: str | None = None

    def includes(self, team: str) -> bool:
        return team in self.teams


class MembershipClient(Protocol):
    """The Member Portal call the membership needs (`MemberPortalPublisher`)."""

    def membership(self) -> tuple[str, tuple[str, ...]]: ...


def membership_note(team: str, source: str | None) -> str:
    """The card's line for a revision made as a team member."""
    where = {
        "platform": "confirmed by the shared platform",
        "platform_cache": "from the shared platform's last answer on this PC",
        "declared": "declared on this PC",
    }.get(source or "", "declared on this PC")
    return f"Revision as a member of team {team} ({where})"


class TeamMembershipStore:
    """The declaration, the platform cache and the lookup, per workspace."""

    def __init__(
        self,
        workspace_root: Path,
        *,
        client: Callable[[], MembershipClient | None] | None = None,
        account: Callable[[], str] | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.settings_path = workspace_root / SETTINGS_FILE
        self.cache_path = workspace_root / CACHE_FILE
        self._client = client if client is not None else (lambda: None)
        self._account = account
        self._clock = clock if clock is not None else (lambda: datetime.now(UTC))
        self._monotonic = monotonic
        self._lock = threading.Lock()
        self._live: tuple[float, TeamMembership] | None = None

    # -- the local declaration -------------------------------------------------

    def declared(self) -> TeamDeclaration:
        try:
            return TeamDeclaration.model_validate_json(self.settings_path.read_bytes())
        except (OSError, ValidationError, ValueError):
            return TeamDeclaration()

    def save_declared(self, request: TeamDeclaration) -> TeamDeclaration:
        checked = TeamDeclaration.model_validate(request)
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        write_atomically(
            self.settings_path, checked.model_dump_json(indent=2).encode("utf-8") + b"\n"
        )
        return checked

    # -- the platform cache ----------------------------------------------------

    def cached(self) -> TeamMembership | None:
        try:
            item = TeamMembership.model_validate_json(self.cache_path.read_bytes())
        except (OSError, ValidationError, ValueError):
            return None
        return item.model_copy(update={"source": "platform_cache"})

    def _save_cache(self, item: TeamMembership) -> None:
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            write_atomically(
                self.cache_path, item.model_dump_json(indent=2).encode("utf-8") + b"\n"
            )
        except OSError:
            pass  # a cache that cannot be written only means asking again

    # -- the lookup ------------------------------------------------------------

    def membership(self, actor: str) -> TeamMembership:
        """The teams `actor` belongs to, by the source order above."""
        platform = self._platform()
        if platform is not None:
            if platform.account is not None and platform.account != actor:
                return TeamMembership(source=platform.source, account=platform.account)
            return platform
        teams = self.declared().declared_teams
        if self._account is not None and self._account() != actor:
            # The declaration is the PC owner's, not another sender's.
            return TeamMembership()
        return TeamMembership(teams=teams, source="declared" if teams else "none")

    def _platform(self) -> TeamMembership | None:
        """The platform's answer, the cache while offline, or None when this
        PC has no platform connection (the declaration then answers)."""
        with self._lock:
            if self._live is not None and self._monotonic() - self._live[0] < LIVE_REUSE_SECONDS:
                return self._live[1]
            client = self._client()
            if client is None:
                return None
            try:
                account, groups = client.membership()
            except Exception as error:  # noqa: BLE001 - classified by its code below
                code = str(getattr(error, "code", "") or "")
                if code in UNCONNECTED_CODES:
                    return None
                if code in OFFLINE_CODES or not code:
                    return self.cached()
                # The platform answered and refused (a revoked login, a
                # disabled account): no teams, and no stale cache either.
                return TeamMembership(source="platform")
            item = TeamMembership(
                teams=tuple(dict.fromkeys(groups)),
                source="platform",
                account=account,
                checked_at=self._clock().isoformat(),
            )
            self._live = (self._monotonic(), item)
            self._save_cache(item)
            return item

    def view(self, actor: str) -> dict[str, object]:
        """What Agent Web Settings shows: the declaration and the current
        answer with its source. Never a credential."""
        current = self.membership(actor)
        return {
            "ok": True,
            "declared_teams": list(self.declared().declared_teams),
            "teams": list(current.teams),
            "source": current.source,
            "account": current.account,
            "checked_at": current.checked_at,
        }
