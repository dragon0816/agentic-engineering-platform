"""The schedule worker uses Agent admission and never replays uncertain work."""

import asyncio
from datetime import UTC, datetime, time
from pathlib import Path
from unittest.mock import AsyncMock, patch

from test_gateway_task_execution import AnswerModel, approved, executor, task
from test_local_agent import agent, company, slow_gateway

from agent.data_policy import DataPolicy
from capabilities.runtime import LocalPolicy
from common.assets import AssetIdentity
from common.execution import ExecutionAuthorization, TraceIdentifiers
from common.scheduling import Recurrence, ScheduleDefinition, ScheduleRecord
from host_runtime.agent import LocalAgent
from host_runtime.schedule_worker import ScheduleWorker
from host_runtime.schedules import SqliteScheduleStore
from host_runtime.state import SqliteLocalState

DUE = datetime(2026, 10, 5, 1, tzinfo=UTC)
TARGET = AssetIdentity(namespace="engineering", name="release-package", version="1.0.0")


def definition(
    *,
    target: AssetIdentity = TARGET,
    kind: str = "workflow",
    owner: str = "engineer",
    inputs: dict[str, str] | None = None,
) -> ScheduleDefinition:
    return ScheduleDefinition.model_validate(
        {
            "schedule_id": "scheduled-release",
            "owner": owner,
            "target_kind": kind,
            "target": target,
            "recurrence": Recurrence(
                kind="weekly", timezone="Asia/Taipei", at=time(9), weekdays=(1,)
            ),
            "runtime_inputs": inputs or {},
        }
    )


def allow(record: ScheduleRecord, trace: TraceIdentifiers) -> ExecutionAuthorization:
    item = record.definition
    return ExecutionAuthorization(
        allowed=True,
        actor=item.owner,
        asset=item.target,
        trace=trace,
        policy_ref="host-schedule-approval",
    )


def test_without_exact_execution_approval_nothing_runs(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(), now=DUE)
        worker = ScheduleWorker(store, resident)
        result = asyncio.run(worker.poll_once(now=DUE))
        assert len(result) == 1
        assert result[0].status == "needs_input"
        assert result[0].result_code == "schedule_approval_required"
        assert runner.bridge.events == ()
        assert resident.runs() == ()
    resident.state.close()


def test_mismatched_approval_cannot_authorize_a_different_target(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    wrong = AssetIdentity(namespace="engineering", name="other", version="1.0.0")

    def mismatched(record: ScheduleRecord, trace: TraceIdentifiers) -> ExecutionAuthorization:
        return ExecutionAuthorization(
            allowed=True,
            actor=record.definition.owner,
            asset=wrong,
            trace=trace,
            policy_ref="wrong-target",
        )

    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(), now=DUE)
        worker = ScheduleWorker(store, resident, authorizer=mismatched)
        result = asyncio.run(worker.poll_once(now=DUE))
        assert result[0].status == "needs_input"
        assert result[0].result_code == "schedule_approval_required"
        assert runner.bridge.events == ()
    resident.state.close()


def test_approved_exact_workflow_runs_through_agent_and_bridge(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(), now=DUE)
        worker = ScheduleWorker(store, resident, authorizer=allow)
        result = asyncio.run(worker.poll_once(now=DUE))
        assert len(result) == 1 and result[0].status == "succeeded"
        assert result[0].result_code == "workflow_succeeded"
        assert runner.bridge.events
        assert len(resident.runs()) == 1
        assert store.pending_claims() == ()
        assert asyncio.run(worker.poll_once(now=DUE)) == ()
    resident.state.close()


def test_schedule_approval_does_not_bypass_bridge_grants(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    runner.bridge.policy = LocalPolicy(())
    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(), now=DUE)
        result = asyncio.run(ScheduleWorker(store, resident, authorizer=allow).poll_once(now=DUE))
        assert result[0].status == "failed"
        assert result[0].result_code == "permission_denied"
        assert runner.bridge.events
        assert all(event.code == "permission_denied" for event in runner.bridge.events)
    resident.state.close()


def test_uninstalled_workflow_and_other_owner_cannot_run(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    missing = AssetIdentity(namespace="engineering", name="not-installed", version="1.0.0")
    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(target=missing), now=DUE)
        result = asyncio.run(ScheduleWorker(store, resident, authorizer=allow).poll_once(now=DUE))
        assert result[0].status == "unavailable"
        assert result[0].result_code == "workflow_not_installed"
        assert runner.bridge.events == ()
    with SqliteScheduleStore(tmp_path / "other.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(owner="other"), now=DUE)
        worker = ScheduleWorker(store, resident, authorizer=allow)
        assert asyncio.run(worker.poll_once(now=DUE)) == ()
        assert store.pending_claims() == ()
    resident.state.close()


def test_ambiguous_dispatch_is_never_replayed_or_overtaken(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(), now=DUE)
        worker = ScheduleWorker(store, resident, authorizer=allow)
        with patch.object(resident, "execute_workflow", new=AsyncMock(side_effect=OSError)) as call:
            first = asyncio.run(worker.poll_once(now=DUE))
            assert first[0].status == "claimed"
            assert asyncio.run(worker.poll_once(now=datetime(2026, 10, 12, 1, tzinfo=UTC))) == ()
            assert call.await_count == 1
        assert store.pending_claims() == first
        assert runner.bridge.events == ()
    # A new process has no idempotency submission to observe, and cannot retry.
    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        worker = ScheduleWorker(store, resident, authorizer=allow)
        assert asyncio.run(worker.poll_once(now=DUE)) == ()
        assert store.pending_claims() == first
    resident.state.close()


def test_same_process_reconciles_workflow_after_caller_timeout(tmp_path: Path) -> None:
    gateway, _ = slow_gateway()
    state = SqliteLocalState(tmp_path / "state.sqlite", bridge_id="bridge-company")
    resident = LocalAgent(company(), gateway, state)

    async def scenario(worker: ScheduleWorker) -> None:
        first = await worker.poll_once(now=DUE)
        assert first[0].status == "claimed", first[0]
        observed = gateway.engine.submitted("engineer", "engineering", first[0].idempotency_key)
        assert observed is not None
        await gateway.engine.wait(observed.run.run_id)
        for _ in range(20):
            if any(
                run.run_id == observed.run.run_id and run.status == "succeeded"
                for run in state.runs()
            ):
                break
            await asyncio.sleep(0.01)
        settled = worker.reconcile_pending()
        assert len(settled) == 1 and settled[0].status == "succeeded"

    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        validation = AssetIdentity(
            namespace="engineering", name="release-validation", version="1.0.0"
        )
        store.create(definition(target=validation), now=DUE)
        worker = ScheduleWorker(store, resident, authorizer=allow, workflow_wait_seconds=0.01)
        asyncio.run(scenario(worker))
        assert store.pending_claims() == ()
    resident.state.close()


def test_exact_task_template_uses_task_policy_and_unique_artifact(tmp_path: Path) -> None:
    model = AnswerModel()
    service, state = executor(tmp_path, model, approved())
    resident = LocalAgent(company(), service.backend.gateway, state, task_executor=service)
    identity = AssetIdentity(namespace="engineering", name="answer-task", version="1.0.0")
    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(target=identity, kind="agent_task"), now=DUE)
        worker = ScheduleWorker(
            store,
            resident,
            authorizer=allow,
            task_templates={identity.key: task()},
        )
        result = asyncio.run(worker.poll_once(now=DUE))
        assert len(result) == 1 and result[0].status == "succeeded"
        assert result[0].result_code == "task_validated"
        assert len(model.calls) == 1
        assert len(state.task_runs("engineer")) == 1
        assert state.task_runs("engineer")[0].task_id.startswith("scheduled-")
        assert len(list((tmp_path / "task-artifacts").iterdir())) == 1
    state.close()


def test_task_gateway_policy_denial_never_calls_model(tmp_path: Path) -> None:
    model = AnswerModel()
    service, state = executor(tmp_path, model, DataPolicy(()))
    resident = LocalAgent(company(), service.backend.gateway, state, task_executor=service)
    identity = AssetIdentity(namespace="engineering", name="answer-task", version="1.0.0")
    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(target=identity, kind="agent_task"), now=DUE)
        worker = ScheduleWorker(
            store,
            resident,
            authorizer=allow,
            task_templates={identity.key: task()},
        )
        result = asyncio.run(worker.poll_once(now=DUE))
        assert result[0].status == "needs_input"
        assert result[0].result_code == "gateway_not_approved"
        assert model.calls == []
        assert state.task_runs("engineer") == ()
    state.close()


def test_task_without_exact_template_is_unavailable(tmp_path: Path) -> None:
    resident, runner = agent(company(), tmp_path)
    identity = AssetIdentity(namespace="engineering", name="answer-task", version="1.0.0")
    with SqliteScheduleStore(tmp_path / "schedules.sqlite", bridge_id="bridge-company") as store:
        store.create(definition(target=identity, kind="agent_task"), now=DUE)
        result = asyncio.run(ScheduleWorker(store, resident, authorizer=allow).poll_once(now=DUE))
        assert result[0].status == "unavailable"
        assert result[0].result_code == "task_not_installed"
        assert runner.bridge.events == ()
    resident.state.close()
