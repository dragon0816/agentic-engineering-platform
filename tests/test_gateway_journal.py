"""Gateway run control over durable evidence: a host that restarts still reaches
its runs through the same entry points, and the journal decides which path applies."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_dispatch import Handler, Input, Output, grant, spec
from test_engine import context, manifest
from test_engine_recovery import FailOnce, Stuck, confirmation
from test_routing import FakeModel
from test_workflow_inputs import step

from agent.gateway import Gateway, RunControlResult
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillRegistry
from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest
from common.execution import RequestContext, ResumePolicy, TraceIdentifiers
from workflow.checkpoints import CheckpointStoreError
from workflow.checkpoints_sqlite import SqliteCheckpointStore
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine
from workflow.journal import RunJournal
from workflow.payloads import FilePayloadStore


def flow(steps: int = 2) -> WorkflowManifest:
    data: list[Any] = [spec().identity.model_dump()]
    for index in range(1, steps):
        data.append(step({"source": "step", "step_index": index - 1, "path": ["count"]}))
    base = manifest([spec().identity]).model_dump()
    base["steps"] = data
    return WorkflowManifest.model_validate(base)


class JournalledHost:
    """One Bridge's durable state; `restart()` builds a brand new Gateway over it."""

    def __init__(self, tmp_path: Path, *, journalled: bool = True) -> None:
        self.path = tmp_path / "checkpoints.sqlite"
        self.payload_root = tmp_path / "payloads"
        self.workflow = flow()
        self.journalled = journalled
        self.stores: list[SqliteCheckpointStore] = []
        self.handler: Handler = Handler()

    def restart(self, handler: Handler | None = None) -> Gateway:
        self.handler = handler if handler is not None else self.handler
        installed = InstalledCapabilities()
        installed.register(
            spec(), self.handler, Input, Output, ExecutionDependencies(central_required=False)
        )
        bridge = BridgeExecutor(installed, LocalPolicy((grant(),)))
        workflows = InstalledWorkflows()
        workflows.register(self.workflow)
        journal = None
        if self.journalled:
            checkpoints = SqliteCheckpointStore(self.path)
            self.stores.append(checkpoints)
            journal = RunJournal(checkpoints, FilePayloadStore(self.payload_root))
        engine = WorkflowEngine(workflows, bridge, journal=journal)
        router = RequestRouter(CommandRouter(SkillRegistry()), model=FakeModel())
        return Gateway(router, bridge, engine)

    def close(self) -> None:
        for store in self.stores:
            store.close()


@pytest.fixture
def journalled_host(tmp_path: Path) -> Any:
    made: list[JournalledHost] = []

    def factory(**changes: Any) -> JournalledHost:
        built = JournalledHost(tmp_path, **changes)
        made.append(built)
        return built

    yield factory
    for built in made:
        built.close()


def start(gateway: Gateway, built: JournalledHost) -> Any:
    return asyncio.run(
        gateway.execute_workflow(
            context(), built.workflow.metadata.identity, {"count": 1}, workflow_timeout_seconds=10
        )
    )


def other_actor() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="trace-2", request_id="request-2", span_id="span-2"),
        actor="someone-else",
        namespace=context().namespace,
        channel="test",
        message="run control",
    )


def test_result_contract_pins_what_each_action_may_report() -> None:
    plan_holder = RunControlResult(action="inspect", run_id="run-1")
    assert plan_holder.source == "unknown" and plan_holder.plan is None
    for invalid in (
        {"action": "suspend", "source": "memory", "suspended_by": "leo"},
        {"action": "resume", "source": "journal", "suspended_by": "leo"},
        {"action": "inspect", "source": "unknown", "plan": None, "suspended_by": "leo"},
    ):
        with pytest.raises(ValidationError):
            RunControlResult.model_validate({"run_id": "run-1", **invalid})


def test_inspect_prefers_this_process_then_falls_back_to_the_journal(
    journalled_host: Any,
) -> None:
    built = journalled_host()
    gateway = built.restart(FailOnce())
    result = start(gateway, built)
    run_id = result.run.run_id

    live = gateway.inspect(context(), run_id)
    assert live.source == "memory" and live.plan is not None
    assert live.suspended_by is None

    # A new process has no history, but the evidence outlived it.
    after_restart = built.restart().inspect(context(), run_id)
    assert after_restart.source == "journal"
    assert after_restart.plan is not None
    assert [s.state for s in after_restart.plan.steps] == ["uncertain", "never_started"]
    assert after_restart.plan.steps == live.plan.steps


def test_an_unjournalled_engine_still_answers_from_memory(journalled_host: Any) -> None:
    built = journalled_host(journalled=False)
    gateway = built.restart(FailOnce())
    result = start(gateway, built)
    assert gateway.inspect(context(), result.run.run_id).source == "memory"
    # A different process keeps nothing, and there is no journal to ask.
    assert built.restart().inspect(context(), result.run.run_id).source == "unknown"


def test_unknown_and_foreign_runs_report_nothing(journalled_host: Any) -> None:
    built = journalled_host()
    gateway = built.restart(FailOnce())
    result = start(gateway, built)
    for probe in (
        gateway.inspect(context(), "run-does-not-exist"),
        gateway.inspect(other_actor(), result.run.run_id),
        gateway.suspend(other_actor(), result.run.run_id, confirmation()),
    ):
        assert probe.source == "unknown"
        assert probe.plan is None and probe.workflow is None
    with pytest.raises(ValidationError):
        gateway.inspect(context(), "not a run id!")


def test_suspend_then_resume_across_a_restart(journalled_host: Any) -> None:
    built = journalled_host()
    first = built.restart(FailOnce())
    result = start(first, built)
    run_id = result.run.run_id
    assert result.run.status == "failed"

    # A different process confirms the old one is gone and continues the run.
    second = built.restart()
    suspended = second.suspend(context(), run_id, confirmation(note="host rebooted"))
    assert suspended.action == "suspend" and suspended.source == "journal"
    assert suspended.suspended_by == "leo"
    assert suspended.plan is not None and suspended.plan.next_step == 0

    resumed = asyncio.run(
        second.resume(context(), run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    )
    assert resumed.action == "resume" and resumed.source == "journal"
    assert resumed.workflow is not None and resumed.workflow.run.status == "succeeded"
    assert resumed.workflow.run.resumed_from == run_id
    # The continuation is itself journalled, so the guard applies to it too.
    assert second.inspect(context(), resumed.workflow.run.run_id).source in {"memory", "journal"}


def test_a_journalled_run_is_continued_once_through_the_gateway(journalled_host: Any) -> None:
    built = journalled_host()
    gateway = built.restart(FailOnce())
    run_id = start(gateway, built).run.run_id
    gateway.suspend(context(), run_id, confirmation())
    policy = ResumePolicy(uncertain="replay_read_only")
    first = asyncio.run(gateway.resume(context(), run_id, policy=policy))
    assert first.workflow is not None and first.workflow.run.status == "succeeded"
    calls = len(built.handler.calls)

    again = asyncio.run(built.restart().resume(context(), run_id, policy=policy))
    assert again.workflow is not None and again.workflow.run.failure is not None
    assert again.workflow.run.failure.code == "checkpoint_already_continued"
    assert len(built.handler.calls) == calls


def test_resuming_without_a_confirmation_is_refused(journalled_host: Any) -> None:
    built = journalled_host()
    gateway = built.restart(FailOnce())
    run_id = start(gateway, built).run.run_id
    refused = asyncio.run(gateway.resume(context(), run_id))
    assert refused.workflow is not None and refused.workflow.run.failure is not None
    assert refused.workflow.run.failure.code == "run_not_suspended"
    assert built.handler.calls == [context()]


def test_an_unjournalled_run_still_resumes_in_memory(journalled_host: Any) -> None:
    built = journalled_host(journalled=False)
    gateway = built.restart(FailOnce())
    run_id = start(gateway, built).run.run_id
    resumed = asyncio.run(
        gateway.resume(context(), run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    )
    assert resumed.source == "memory"
    assert resumed.workflow is not None and resumed.workflow.run.status == "succeeded"
    assert resumed.workflow.run.resumed_from == run_id


def test_a_live_run_cannot_be_suspended_through_the_gateway(journalled_host: Any) -> None:
    async def scenario() -> None:
        built = journalled_host()
        gateway = built.restart(Stuck())
        started = await gateway.execute_workflow(
            context(), built.workflow.metadata.identity, {"count": 1}, workflow_timeout_seconds=0.01
        )
        try:
            with pytest.raises(CheckpointStoreError, match="invalid_transition"):
                gateway.suspend(context(), started.run.run_id, confirmation())
        finally:
            gateway.engine._tasks[started.run.run_id].cancel()
            await gateway.engine.wait(started.run.run_id)

    asyncio.run(scenario())


def test_run_control_still_adds_no_authority(journalled_host: Any) -> None:
    built = journalled_host()
    gateway = built.restart(FailOnce())
    run_id = start(gateway, built).run.run_id
    gateway.suspend(context(), run_id, confirmation())

    # A new process whose policy grants nothing cannot continue the run.
    denied = built.restart()
    denied.engine.bridge.policy = LocalPolicy(())
    result = asyncio.run(
        denied.resume(context(), run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    )
    assert result.workflow is not None and result.workflow.run.failure is not None
    assert result.workflow.run.failure.code == "permission_denied"
