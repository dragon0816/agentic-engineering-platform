"""Serializable local schedule intent, without execution authority."""

import hashlib
import json
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal, Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, JsonValue, field_validator, model_validator

from common.assets import AssetIdentity, reject_embedded_secrets
from common.base import Contract, Symbol
from common.execution import IdempotencyKey


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


class ScheduledRun(Contract):
    schedule_id: Symbol
    due_at: datetime
    idempotency_key: IdempotencyKey
    claimed_at: datetime
    status: Literal["claimed", "succeeded", "failed", "needs_input", "unavailable"]
    result_code: Symbol | None = None

    @field_validator("due_at", "claimed_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        return _utc(value)

    @model_validator(mode="after")
    def outcome_consistency(self) -> Self:
        if (self.status == "claimed") != (self.result_code is None):
            raise ValueError("only an unfinished claim omits its result code")
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
