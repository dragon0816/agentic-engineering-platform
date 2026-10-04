"""Schedule execution grants, store schema v2 and the per-occurrence policy.

A saved schedule is not permission. These tests pin the owner decisions of
2026-10-04: `read` runs unattended with a schedule grant; `write`/`execute`
also need the exact Bridge grant; `external_side_effect` always waits for a
person on every run.
"""

import asyncio
import sqlite3
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from typing import Any

import pytest
from evaluation_runner import GatewayRunner, Probe, RecordingHandler, Report, grants
from pydantic import ValidationError
from test_local_agent import agent, company

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityGrant, LocalPolicy
from common.assets import AssetIdentity, ExecutionDependencies, WorkflowManifest
from common.execution import SideEffect
from common.scheduling import (
    Recurrence,
    ScheduleDefinition,
    ScheduleExecutionGrant,
    ScheduleGrantRecord,
    ScheduleOperatorDecision,
    ScheduleRecord,
    max_side_effect,
)
from host_runtime.agent import LocalAgent
from host_runtime.schedule_policy import ScheduleGrantAuthorizer
from host_runtime.schedule_worker import ScheduleWorker, _trace
from host_runtime.schedules import SCHEMA_VERSION, ScheduleStoreError, SqliteScheduleStore

DUE = datetime(2026, 10, 5, 1, tzinfo=UTC)  # Monday 09:00 Asia/Taipei
READ = AssetIdentity(namespace="engineering", name="release-validation", version="1.0.0")
SEND = AssetIdentity(namespace="engineering", name="release-package", version="1.0.0")
WRITE = AssetIdentity(namespace="engineering", name="write-report", version="1.0.0")
WRITE_CAPABILITY = AssetIdentity(namespace="engineering", name="write-workbook", version="1.0.0")


def definition(target: AssetIdentity = READ, schedule_id: str = "weekly") -> ScheduleDefinition:
    return ScheduleDefinition(
        schedule_id=schedule_id,
        owner="engineer",
        target_kind="workflow",
        target=target,
        recurrence=Recurrence(kind="weekly", timezone="Asia/Taipei", at=time(9), weekdays=(1,)),
    )


def grant(
    target: AssetIdentity = READ,
    effect: SideEffect = "read",
    *,
    schedule_id: str = "weekly",
    expires_at: datetime | None = None,
    approved_at: datetime = DUE - timedelta(days=1),
) -> ScheduleExecutionGrant:
    return ScheduleExecutionGrant(
        schedule_id=schedule_id,
        owner="engineer",
        target_kind="workflow",
        target=target,
        max_side_effect=effect,
        policy_ref="owner-schedule-grant",
        approved_by="engineer",
        approved_at=approved_at,
        expires_at=expires_at,
    )


def write_spec() -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": WRITE_CAPABILITY.model_dump(),
            "name": "engineering.write_workbook",
            "description": "Inert workbook write fixture",
            "input_contract": "engineering.validate-release.input.v1",
            "output_contract": "engineering.validate-release.output.v1",
            "side_effect": "write",
            "policy": {
                "required_permissions": ["excel.write"],
                "policy_refs": ["excel-write-policy"],
                "approval_required": True,
            },
        }
    )


def write_workflow() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": WRITE.model_dump(),
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "private",
            },
            "description": "Inert one-step write fixture",
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False},
            "input_contract": "engineering.validate-release.input.v1",
            "output_contract": "engineering.validate-release.output.v1",
            "steps": [WRITE_CAPABILITY.model_dump()],
        }
    )


WRITE_GRANT = CapabilityGrant(
    actor="engineer",
    asset=WRITE_CAPABILITY,
    permissions=("excel.write",),
    policy_refs=("excel-write-policy",),
    approval_ref="owner-excel-approval",
)


def resident_with_write(
    tmp_path: Path, *, bridge_write_grant: bool
) -> tuple[LocalAgent, GatewayRunner, RecordingHandler]:
    resident, runner = agent(company(), tmp_path)
    writer = RecordingHandler()
    runner.installed.register(
        write_spec(), writer, Probe, Report, ExecutionDependencies(central_required=False)
    )
    runner.workflows.register(write_workflow())
    runner.bridge.policy = LocalPolicy(
        grants() + ((WRITE_GRANT,) if bridge_write_grant else ())
    )
    return resident, runner, writer


def worker(store: SqliteScheduleStore, resident: LocalAgent) -> ScheduleWorker:
    return ScheduleWorker(
        store,
        resident,
        authorizer=ScheduleGrantAuthorizer(store, resident),
        workflow_wait_seconds=5,
    )


# -- contracts ---------------------------------------------------------------


def test_grant_contract_is_owner_approved_bounded_and_credential_free() -> None:
    item = grant()
    assert ScheduleExecutionGrant.model_validate_json(item.model_dump_json()) == item
    assert item.covers(definition())
    assert not item.covers(definition(SEND))
    payload: dict[str, Any] = item.model_dump()
    with pytest.raises(ValidationError):
        ScheduleExecutionGrant.model_validate({**payload, "approved_by": "someone-else"})
    with pytest.raises(ValidationError):
        ScheduleExecutionGrant.model_validate({**payload, "expires_at": item.approved_at})
    with pytest.raises(ValidationError):
        ScheduleExecutionGrant.model_validate({**payload, "policy_ref": "password=hunter22"})
    with pytest.raises(ValidationError):
        ScheduleExecutionGrant.model_validate({**payload, "max_side_effect": "anything"})
    with pytest.raises(ValidationError):
        ScheduleExecutionGrant.model_validate({**payload, "approved_at": datetime(2026, 10, 1)})
    assert grant(expires_at=DUE).expired(DUE)
    assert not grant(expires_at=DUE).expired(DUE - timedelta(seconds=1))
    assert max_side_effect(()) == "read"
    assert max_side_effect(("write", "read", "execute")) == "execute"
    assert max_side_effect(("external_side_effect", "write")) == "external_side_effect"


def test_revocation_and_decisions_are_attributed() -> None:
    with pytest.raises(ValidationError):
        ScheduleGrantRecord(grant=grant(), revoked_at=DUE)
    with pytest.raises(ValidationError):
        ScheduleOperatorDecision(
            idempotency_key="schedule:abc",
            schedule_id="weekly",
            kind="approve",
            outcome="succeeded",
            decided_by="engineer",
            decided_at=DUE,
        )
    with pytest.raises(ValidationError):
        ScheduleOperatorDecision(
            idempotency_key="schedule:abc",
            schedule_id="weekly",
            kind="resolve",
            outcome="not_run",
            decided_by="engineer",
            decided_at=DUE,
            note="api_key=abc123",
        )


# -- store schema v2 ---------------------------------------------------------


def test_a_version_one_store_is_migrated_and_a_newer_one_refused(tmp_path: Path) -> None:
    path = tmp_path / "schedules.sqlite"
    record = ScheduleRecord(definition=definition(), status="active", next_due_at=DUE)
    conn = sqlite3.connect(path)
    conn.executescript(
        "CREATE TABLE schedule_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);"
        "CREATE TABLE schedules (schedule_id TEXT PRIMARY KEY, owner TEXT NOT NULL,"
        " status TEXT NOT NULL, next_due_at TEXT NOT NULL, record TEXT NOT NULL);"
        "CREATE TABLE scheduled_runs (idempotency_key TEXT PRIMARY KEY,"
        " schedule_id TEXT NOT NULL, due_at TEXT NOT NULL, status TEXT NOT NULL,"
        " record TEXT NOT NULL, UNIQUE (schedule_id, due_at));"
        "INSERT INTO schedule_meta VALUES ('schema_version', '1');"
        "INSERT INTO schedule_meta VALUES ('bridge_id', 'bridge-company');"
    )
    conn.execute(
        "INSERT INTO schedules VALUES (?, ?, ?, ?, ?)",
        ("weekly", "engineer", "active", DUE.isoformat(), record.model_dump_json()),
    )
    conn.commit()
    conn.close()
    with SqliteScheduleStore(path, bridge_id="bridge-company") as store:
        assert store.get("weekly", owner="engineer") == record
        assert store.active_grant("weekly", owner="engineer") is None
        store.grant(grant())
        assert store.active_grant("weekly", owner="engineer") is not None
    conn = sqlite3.connect(path)
    assert conn.execute(
        "SELECT value FROM schedule_meta WHERE key = 'schema_version'"
    ).fetchone() == (SCHEMA_VERSION,)
    conn.execute("UPDATE schedule_meta SET value = '99' WHERE key = 'schema_version'")
    conn.commit()
    conn.close()
    with pytest.raises(ScheduleStoreError, match="unavailable"):
        SqliteScheduleStore(path, bridge_id="bridge-company")


def test_grants_are_exact_replaced_revoked_and_kept_for_audit(tmp_path: Path) -> None:
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(), now=DUE - timedelta(days=2))
        with pytest.raises(ScheduleStoreError, match="grant_mismatch"):
            store.grant(grant(SEND))
        with pytest.raises(ScheduleStoreError, match="unknown"):
            store.grant(grant(schedule_id="other"))
        first = store.grant(grant())
        second = store.grant(grant(effect="write", approved_at=DUE - timedelta(hours=1)))
        active = store.active_grant("weekly", owner="engineer")
        assert active == second and active.grant.max_side_effect == "write"
        history = store.grant_history("weekly", owner="engineer")
        assert history[0] == second
        assert history[1].grant == first.grant and history[1].revoked_by == "engineer"
        revoked = store.revoke("weekly", owner="engineer", revoked_by="engineer", now=DUE)
        assert revoked.revoked_at == DUE and not revoked.active
        assert store.active_grant("weekly", owner="engineer") is None
        with pytest.raises(ScheduleStoreError, match="no_grant"):
            store.revoke("weekly", owner="engineer", revoked_by="engineer", now=DUE)
        with pytest.raises(ScheduleStoreError, match="owner_mismatch"):
            store.active_grant("weekly", owner="other")


# -- the policy --------------------------------------------------------------


def test_without_a_schedule_grant_nothing_runs(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(), now=DUE)
        (result,) = asyncio.run(worker(store, resident).poll_once(now=DUE))
        assert (result.status, result.result_code) == ("needs_input", "schedule_grant_missing")
        assert runner.bridge.events == ()
    resident.state.close()


def test_read_runs_unattended_with_a_schedule_grant(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(), now=DUE)
        store.grant(grant())
        (result,) = asyncio.run(worker(store, resident).poll_once(now=DUE))
        assert (result.status, result.result_code) == ("succeeded", "workflow_succeeded")
        assert result.side_effect == "read"
        assert len(runner.bridge.events) == 1
    resident.state.close()


def test_expired_or_revoked_grant_refuses_and_dispatches_nothing(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(), now=DUE)
        store.grant(grant(expires_at=DUE))
        (expired,) = asyncio.run(worker(store, resident).poll_once(now=DUE))
        assert (expired.status, expired.result_code) == ("needs_input", "schedule_grant_expired")
        store.grant(grant(approved_at=DUE + timedelta(hours=1)))
        store.revoke(
            "weekly", owner="engineer", revoked_by="engineer", now=DUE + timedelta(hours=2)
        )
        later = DUE + timedelta(days=7)
        (revoked,) = asyncio.run(worker(store, resident).poll_once(now=later))
        assert (revoked.status, revoked.result_code) == ("needs_input", "schedule_grant_missing")
        assert runner.bridge.events == ()
    resident.state.close()


def test_a_grant_for_another_target_does_not_authorize(tmp_path: Path) -> None:
    resident, _runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        record = store.create(definition(), now=DUE)
        store.grant(grant())
        policy = ScheduleGrantAuthorizer(store, resident)
        changed = record.model_copy(
            update={"definition": record.definition.model_copy(update={"target": SEND})}
        )
        claim = store.claim_due(now=DUE)[0]
        decision = policy.decide(changed, _trace(claim), run_approved=True, now=DUE)
        assert not decision.allowed and decision.code == "schedule_grant_mismatch"
        allowed = policy.decide(record, _trace(claim), run_approved=False, now=DUE)
        assert allowed.allowed and allowed.authorization.policy_ref == "owner-schedule-grant"
    resident.state.close()


def test_write_needs_both_the_bridge_grant_and_a_grant_naming_write(tmp_path: Path) -> None:
    resident, _runner, writer = resident_with_write(tmp_path, bridge_write_grant=False)
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(WRITE), now=DUE)
        store.grant(grant(WRITE, "read"))
        (above,) = asyncio.run(worker(store, resident).poll_once(now=DUE))
        assert (above.status, above.result_code) == ("needs_input", "schedule_effect_above_grant")
        assert above.side_effect == "write"
        store.grant(grant(WRITE, "write", approved_at=DUE))
        week = DUE + timedelta(days=7)
        (missing,) = asyncio.run(worker(store, resident).poll_once(now=week))
        assert (missing.status, missing.result_code) == ("needs_input", "bridge_grant_missing")
        assert writer.calls == 0
    resident.state.close()


def test_write_runs_unattended_with_both_grants(tmp_path: Path) -> None:
    resident, _runner, writer = resident_with_write(tmp_path, bridge_write_grant=True)
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(WRITE), now=DUE)
        store.grant(grant(WRITE, "write"))
        (result,) = asyncio.run(worker(store, resident).poll_once(now=DUE))
        assert (result.status, result.side_effect) == ("succeeded", "write")
        assert writer.calls == 1
    resident.state.close()


def test_send_class_never_runs_unattended_even_with_every_grant(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(SEND), now=DUE)
        store.grant(grant(SEND, "execute"))
        (above,) = asyncio.run(worker(store, resident).poll_once(now=DUE))
        assert above.result_code == "schedule_effect_above_grant"
        store.grant(grant(SEND, "external_side_effect", approved_at=DUE))
        week = DUE + timedelta(days=7)
        (waiting,) = asyncio.run(worker(store, resident).poll_once(now=week))
        assert (waiting.status, waiting.result_code) == (
            "awaiting_approval",
            "run_approval_required",
        )
        assert waiting.side_effect == "external_side_effect"
        # Waiting does not block, dispatch nothing, and is never auto-sent.
        assert asyncio.run(worker(store, resident).poll_once(now=week)) == ()
        assert store.pending_claims() == ()
        assert runner.bridge.events == ()
        assert store.awaiting_approval(owner="engineer") == (waiting,)
    resident.state.close()


def test_a_person_approves_one_run_which_passes_every_check_again(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(SEND), now=DUE)
        store.grant(grant(SEND, "external_side_effect"))
        (waiting,) = asyncio.run(worker(store, resident).poll_once(now=DUE))
        with pytest.raises(ScheduleStoreError, match="owner_mismatch"):
            asyncio.run(
                worker(store, resident).run_approved(
                    waiting.idempotency_key, decided_by="other", now=DUE
                )
            )
        done = asyncio.run(
            worker(store, resident).run_approved(
                waiting.idempotency_key, decided_by="engineer", now=DUE, note="checked draft"
            )
        )
        assert (done.status, done.result_code) == ("succeeded", "workflow_succeeded")
        assert runner.publisher.calls == 1
        (decision,) = store.decisions("weekly", owner="engineer")
        assert (decision.kind, decision.decided_by, decision.note) == (
            "approve",
            "engineer",
            "checked draft",
        )
        with pytest.raises(ScheduleStoreError, match="not_awaiting_approval"):
            asyncio.run(
                worker(store, resident).run_approved(
                    waiting.idempotency_key, decided_by="engineer", now=DUE
                )
            )
    resident.state.close()


def test_approval_after_revocation_or_denial_dispatches_nothing(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(SEND), now=DUE)
        store.grant(grant(SEND, "external_side_effect"))
        (first,) = asyncio.run(worker(store, resident).poll_once(now=DUE))
        store.revoke("weekly", owner="engineer", revoked_by="engineer", now=DUE)
        refused = asyncio.run(
            worker(store, resident).run_approved(
                first.idempotency_key, decided_by="engineer", now=DUE
            )
        )
        assert (refused.status, refused.result_code) == ("needs_input", "schedule_grant_missing")
        store.grant(grant(SEND, "external_side_effect", approved_at=DUE))
        week = DUE + timedelta(days=7)
        (second,) = asyncio.run(worker(store, resident).poll_once(now=week))
        denied = store.deny_run(
            second.idempotency_key, owner="engineer", decided_by="engineer", now=week
        )
        assert (denied.status, denied.result_code) == ("needs_input", "run_approval_denied")
        assert runner.bridge.events == ()
    resident.state.close()


def test_a_newer_occurrence_supersedes_an_unanswered_approval(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "s.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(SEND), now=DUE)
        store.grant(grant(SEND, "external_side_effect"))
        (first,) = asyncio.run(worker(store, resident).poll_once(now=DUE))
        week = DUE + timedelta(days=7)
        (second,) = asyncio.run(worker(store, resident).poll_once(now=week))
        old = store.run(first.idempotency_key, owner="engineer")
        assert (old.status, old.result_code) == ("needs_input", "run_approval_superseded")
        assert store.awaiting_approval(owner="engineer") == (second,)
        assert runner.bridge.events == ()
    resident.state.close()
