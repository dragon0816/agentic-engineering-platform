"""Serializable local schedule intent, and the owner's separate execution grant.

A `ScheduleDefinition` is intent only. Permission to run it unattended is a
separate Host-owned `ScheduleExecutionGrant` that the owner creates through a
trusted local control; neither a definition, a published asset nor a model
response can supply one.
"""

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, JsonValue, field_validator, model_validator

from common.assets import AssetIdentity, reject_embedded_secrets
from common.base import Contract, Symbol, Text
from common.execution import IdempotencyKey, SideEffect

#: Effect classes in increasing order of consequence. A schedule grant names
#: the highest class it permits; anything above it is refused.
SIDE_EFFECT_RANK: dict[str, int] = {
    "read": 0,
    "write": 1,
    "execute": 2,
    "external_side_effect": 3,
}


def max_side_effect(effects: Iterable[SideEffect]) -> SideEffect:
    """The most consequential class among `effects`; `read` for none."""
    highest: SideEffect = "read"
    for effect in effects:
        if SIDE_EFFECT_RANK[effect] > SIDE_EFFECT_RANK[highest]:
            highest = effect
    return highest


def within_side_effect(effect: SideEffect, limit: SideEffect) -> bool:
    return SIDE_EFFECT_RANK[effect] <= SIDE_EFFECT_RANK[limit]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("schedule timestamps require a timezone")
    return value.astimezone(UTC)


class Recurrence(Contract):
    """A local wall-clock time. Missing DST times are skipped, folds run once."""

    kind: Literal["daily", "weekly"]
    timezone: str
    at: time
    weekdays: tuple[int, ...] = ()  # ISO: Monday=1, Sunday=7

    @field_validator("timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("unknown IANA timezone") from None
        return value

    @model_validator(mode="after")
    def valid_clock(self) -> Self:
        if self.at.tzinfo is not None or self.at.second or self.at.microsecond:
            raise ValueError("at must be a local HH:MM without an offset")
        if self.kind == "daily" and self.weekdays:
            raise ValueError("daily recurrence has no weekdays")
        if self.kind == "weekly" and (
            not self.weekdays
            or any(day < 1 or day > 7 for day in self.weekdays)
            or len(set(self.weekdays)) != len(self.weekdays)
        ):
            raise ValueError("weekly recurrence needs unique ISO weekdays")
        return self


class ScheduleDefinition(Contract):
    """Exact installed target and static inputs; no credential or approval claim."""

    schedule_id: Symbol
    owner: Symbol
    target_kind: Literal["workflow", "agent_task"]
    target: AssetIdentity
    recurrence: Recurrence
    runtime_inputs: dict[Symbol, JsonValue] = Field(default_factory=dict, max_length=50)
    initial_status: Literal["active", "paused"] = "active"

    @model_validator(mode="after")
    def no_embedded_credentials(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        if len(json.dumps(self.runtime_inputs, ensure_ascii=False).encode("utf-8")) > 65_536:
            raise ValueError("scheduled runtime inputs exceed 64 KiB")
        return self


class ScheduleRecord(Contract):
    definition: ScheduleDefinition
    status: Literal["active", "paused"]
    next_due_at: datetime

    @field_validator("next_due_at")
    @classmethod
    def aware_due(cls, value: datetime) -> datetime:
        return _utc(value)


ScheduledRunStatus = Literal[
    "claimed", "awaiting_approval", "succeeded", "failed", "needs_input", "unavailable"
]


class ScheduledRun(Contract):
    """One occurrence. `claimed` may have dispatched and blocks the schedule;
    `awaiting_approval` dispatched nothing and waits for a per-run human
    decision; the other states are terminal."""

    schedule_id: Symbol
    due_at: datetime
    idempotency_key: IdempotencyKey
    claimed_at: datetime
    status: ScheduledRunStatus
    result_code: Symbol | None = None
    # The highest effect class the target declared when it was evaluated.
    side_effect: SideEffect | None = None

    @field_validator("due_at", "claimed_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def outcome_consistency(self) -> Self:
        if (self.status == "claimed") != (self.result_code is None):
            raise ValueError("only an unfinished claim omits its result code")
        return self


class ScheduleExecutionGrant(Contract):
    """The owner's standing permission for one schedule's exact target.

    Host-owned and created only by the owner through a trusted local control
    (CLI or Agent Web). It never comes from a schedule definition, an asset or
    a model. It permits unattended execution up to `max_side_effect`; Bridge
    capability grants are still required for every step, and an
    `external_side_effect` target still needs a human decision on every run.
    """

    schedule_id: Symbol
    owner: Symbol
    target_kind: Literal["workflow", "agent_task"]
    target: AssetIdentity
    max_side_effect: SideEffect
    policy_ref: Text
    approved_by: Symbol
    approved_at: datetime
    expires_at: datetime | None = None

    @field_validator("approved_at", "expires_at")
    @classmethod
    def aware_timestamp(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @model_validator(mode="after")
    def owner_approves_a_bounded_grant(self) -> Self:
        if self.approved_by != self.owner:
            raise ValueError("only the schedule owner may grant its execution")
        if self.expires_at is not None and self.expires_at <= self.approved_at:
            raise ValueError("a grant must expire after it was approved")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self

    def covers(self, definition: ScheduleDefinition) -> bool:
        return (
            self.schedule_id == definition.schedule_id
            and self.owner == definition.owner
            and self.target_kind == definition.target_kind
            and self.target == definition.target
        )

    def expired(self, now: datetime) -> bool:
        return self.expires_at is not None and _utc(now) >= self.expires_at


class ScheduleGrantRecord(Contract):
    """A grant and, once revoked, who revoked it and when. Kept for audit."""

    grant: ScheduleExecutionGrant
    revoked_at: datetime | None = None
    revoked_by: Symbol | None = None

    @field_validator("revoked_at")
    @classmethod
    def aware_revocation(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _utc(value)

    @model_validator(mode="after")
    def revocation_is_attributed(self) -> Self:
        if (self.revoked_at is None) != (self.revoked_by is None):
            raise ValueError("a revocation names who revoked the grant and when")
        return self

    @property
    def active(self) -> bool:
        return self.revoked_at is None


ResolutionOutcome = Literal["succeeded", "failed", "not_run"]


class ScheduleOperatorDecision(Contract):
    """A person's decision on one occurrence: resolving an uncertain claim,
    or approving/denying a run that needs per-run approval."""

    idempotency_key: IdempotencyKey
    schedule_id: Symbol
    kind: Literal["resolve", "approve", "deny"]
    outcome: Literal["succeeded", "failed", "not_run", "approved", "denied"]
    decided_by: Symbol
    decided_at: datetime
    note: Text | None = Field(default=None, max_length=500)

    @field_validator("decided_at")
    @classmethod
    def aware_decision(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def consistent_and_credential_free(self) -> Self:
        allowed = {
            "resolve": {"succeeded", "failed", "not_run"},
            "approve": {"approved"},
            "deny": {"denied"},
        }[self.kind]
        if self.outcome not in allowed:
            raise ValueError("decision outcome does not match its kind")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


def next_occurrence(
    recurrence: Recurrence, *, after: datetime, inclusive: bool = False
) -> datetime:
    """Return the next UTC occurrence, choosing fold=0 and skipping DST gaps."""
    rule = Recurrence.model_validate(recurrence)
    point = _utc(after)
    zone = ZoneInfo(rule.timezone)
    local_day = point.astimezone(zone).date()
    for offset in range(15):
        day: date = local_day + timedelta(days=offset)
        if rule.kind == "weekly" and day.isoweekday() not in rule.weekdays:
            continue
        wall = datetime.combine(day, rule.at).replace(tzinfo=zone, fold=0)
        candidate = wall.astimezone(UTC)
        # A round trip detects a nonexistent local clock time at a DST jump.
        if candidate.astimezone(zone).replace(tzinfo=None) != wall.replace(tzinfo=None):
            continue
        if candidate > point or (inclusive and candidate == point):
            return candidate
    raise ValueError("no occurrence within the next two weeks")


def claim_key(schedule_id: str, due_at: datetime) -> str:
    """Stable across process restarts, with no input or credential bytes."""
    digest = hashlib.sha256(f"{schedule_id}:{_utc(due_at).isoformat()}".encode()).hexdigest()
    return f"schedule:{digest}"
