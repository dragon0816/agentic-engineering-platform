"""Schedule contracts and durable claim behavior, without target execution."""

from datetime import UTC, datetime, time
from pathlib import Path
from typing import Literal

import pytest
from pydantic import ValidationError

from common.assets import AssetIdentity
from common.scheduling import Recurrence, ScheduleDefinition, claim_key, next_occurrence
from host_runtime.schedules import ScheduleStoreError, SqliteScheduleStore


def definition(
    *,
    schedule_id: str = "weekly-report",
    initially_active: bool = True,
    kind: Literal["workflow", "agent_task"] = "workflow",
) -> ScheduleDefinition:
    return ScheduleDefinition(
        schedule_id=schedule_id,
        owner="engineer",
        target_kind=kind,
        target=AssetIdentity(namespace="engineering", name="weekly-report", version="1.0.0"),
        recurrence=Recurrence(
            kind="weekly", timezone="Asia/Taipei", at=time(9, 0), weekdays=(1,)
        ),
        runtime_inputs={"week": "2026_40W"},
        initial_status="active" if initially_active else "paused",
    )


def test_contract_pins_target_and_refuses_credentials() -> None:
    item = definition()
    assert ScheduleDefinition.model_validate_json(item.model_dump_json()) == item
    assert item.target.version == "1.0.0"
    with pytest.raises(ValidationError):
        ScheduleDefinition.model_validate({**item.model_dump(), "target_kind": "arbitrary"})
    with pytest.raises(ValidationError):
        ScheduleDefinition.model_validate(
            {**item.model_dump(), "runtime_inputs": {"api_key": "secret"}}
        )
    with pytest.raises(ValidationError):
        ScheduleDefinition.model_validate(
            {**item.model_dump(), "runtime_inputs": {"content": "x" * 65_537}}
        )


def test_recurrence_validates_clock_weekdays_and_zone() -> None:
    with pytest.raises(ValidationError):
        Recurrence(kind="weekly", timezone="Asia/Taipei", at=time(9), weekdays=())
    with pytest.raises(ValidationError):
        Recurrence(kind="daily", timezone="Asia/Taipei", at=time(9), weekdays=(1,))
    with pytest.raises(ValidationError):
        Recurrence(kind="daily", timezone="Mars/Olympus", at=time(9))
    with pytest.raises(ValueError):
        next_occurrence(
            Recurrence(kind="daily", timezone="Asia/Taipei", at=time(9)),
            after=datetime(2026, 10, 1),
        )


def test_dst_gap_skips_a_day_and_fold_runs_once() -> None:
    spring = Recurrence(kind="daily", timezone="America/New_York", at=time(2, 30))
    assert next_occurrence(spring, after=datetime(2026, 3, 8, 6, tzinfo=UTC)) == datetime(
        2026, 3, 9, 6, 30, tzinfo=UTC
    )
    autumn = Recurrence(kind="daily", timezone="America/New_York", at=time(1, 30))
    first = next_occurrence(autumn, after=datetime(2026, 11, 1, 5, tzinfo=UTC))
    assert first == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert next_occurrence(autumn, after=first) == datetime(2026, 11, 2, 6, 30, tzinfo=UTC)


def test_claim_is_durable_exact_and_reopen_does_not_duplicate(tmp_path: Path) -> None:
    path = tmp_path / "schedules.sqlite"
    before = datetime(2026, 9, 28, 0, 0, tzinfo=UTC)  # Monday 08:00 Taipei
    due = datetime(2026, 9, 28, 1, 0, tzinfo=UTC)
    with SqliteScheduleStore(path, bridge_id="bridge-company") as store:
        record = store.create(definition(), now=before)
        assert record.next_due_at == due
        assert store.claim_due(now=before) == ()
        claims = store.claim_due(now=due)
        assert len(claims) == 1
        assert claims[0].idempotency_key == claim_key("weekly-report", due)
        assert store.claim_due(now=due) == ()
        assert store.get("weekly-report", owner="engineer").next_due_at == datetime(
            2026, 10, 5, 1, tzinfo=UTC
        )
    with SqliteScheduleStore(path, bridge_id="bridge-company") as reopened:
        assert reopened.pending_claims() == claims
        assert reopened.claim_due(now=due) == ()
        done = reopened.record_outcome(
            claims[0].idempotency_key,
            owner="engineer",
            status="succeeded",
            result_code="workflow_succeeded",
        )
        assert done.status == "succeeded"
        assert reopened.pending_claims() == ()
        assert reopened.history("weekly-report", owner="engineer") == (done,)
        assert reopened.record_outcome(
            claims[0].idempotency_key,
            owner="engineer",
            status="succeeded",
            result_code="workflow_succeeded",
        ) == done
        with pytest.raises(ScheduleStoreError, match="outcome_conflict"):
            reopened.record_outcome(
                claims[0].idempotency_key,
                owner="engineer",
                status="failed",
                result_code="wrong",
            )
        with pytest.raises(ScheduleStoreError, match="owner_mismatch"):
            reopened.history("weekly-report", owner="other")


def test_pause_resume_skips_missed_runs_and_owner_is_fixed(tmp_path: Path) -> None:
    path = tmp_path / "schedules.sqlite"
    with SqliteScheduleStore(path, bridge_id="bridge-company") as store:
        store.create(definition(initially_active=False), now=datetime(2026, 9, 28, tzinfo=UTC))
        assert store.claim_due(now=datetime(2026, 10, 10, tzinfo=UTC)) == ()
        with pytest.raises(ScheduleStoreError, match="owner_mismatch"):
            store.get("weekly-report", owner="other")
        resumed = store.set_active(
            "weekly-report", owner="engineer", active=True, now=datetime(2026, 10, 10, tzinfo=UTC)
        )
        assert resumed.next_due_at == datetime(2026, 10, 12, 1, tzinfo=UTC)
        assert store.claim_due(now=datetime(2026, 10, 10, tzinfo=UTC)) == ()
        assert store.list(owner="engineer") == (resumed,)
        assert store.list(owner="other") == ()
        with pytest.raises(ScheduleStoreError, match="exists"):
            store.create(definition(), now=datetime(2026, 10, 10, tzinfo=UTC))
    with pytest.raises(ScheduleStoreError, match="unavailable"):
        SqliteScheduleStore(path, bridge_id="other-bridge")
