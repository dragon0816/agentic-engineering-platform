"""Engine recovery: write-ahead evidence on the real execution path, manual
suspension, and continuing a run in a process that never started it."""

import asyncio
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_dispatch import Handler, Input, Output, grant, spec
from test_engine import context, manifest
from test_workflow_inputs import step

from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.checkpoints import CheckpointOwner
from common.execution import RequestContext, ResumePolicy
from workflow.checkpoints import CheckpointStoreError
from workflow.checkpoints_sqlite import SqliteCheckpointStore
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine
from workflow.journal import RunJournal, SuspensionConfirmation
from workflow.payloads import FilePayloadStore


class FailOnce(Handler):
    """Fails the first call only, so a retry after recovery succeeds."""

    async def __call__(self, ctx: RequestContext, inputs: Contract) -> Contract:
        if not self.calls:
            self.calls.append(ctx)
            raise RuntimeError("private error payload")
        return await super().__call__(ctx, inputs)


class Stuck(Handler):
    async def __call__(self, ctx: RequestContext, inputs: Contract) -> Contract:
        await asyncio.sleep(30)
        return await super().__call__(ctx, inputs)


def flow(steps: int = 2) -> WorkflowManifest:
    """Chained steps, so recovery must restore an earlier result to continue."""
    data: list[Any] = [spec().identity.model_dump()]
    for index in range(1, steps):
        data.append(step({"source": "step", "step_index": index - 1, "path": ["count"]}))
    base = manifest([spec().identity]).model_dump()
    base["steps"] = data
    return WorkflowManifest.model_validate(base)


def owner() -> CheckpointOwner:
    return CheckpointOwner(actor=context().actor, namespace=context().namespace)


def confirmation(**changes: Any) -> SuspensionConfirmation:
    return SuspensionConfirmation.model_validate(
        {"operator": "leo", "process_confirmed_stopped": True, **changes}
    )


class Host:
    """One Bridge's durable state; `restart()` is a brand new engine over it."""

    def __init__(self, tmp_path: Path, workflow: WorkflowManifest) -> None:
        self.path = tmp_path / "checkpoints.sqlite"
        self.payload_root = tmp_path / "payloads"
        self.workflow = workflow
        self.stores: list[SqliteCheckpointStore] = []
        self.handler: Handler = Handler()

    def restart(self, handler: Handler | None = None, *, granted: bool = True) -> WorkflowEngine:
        self.handler = handler if handler is not None else self.handler
        installed = InstalledCapabilities()
        installed.register(
            spec(), self.handler, Input, Output, ExecutionDependencies(central_required=False)
        )
        bridge = BridgeExecutor(installed, LocalPolicy((grant(),) if granted else ()))
        workflows = InstalledWorkflows()
        workflows.register(self.workflow)
        checkpoints = SqliteCheckpointStore(self.path)
        self.stores.append(checkpoints)
        journal = RunJournal(checkpoints, FilePayloadStore(self.payload_root))
        return WorkflowEngine(workflows, bridge, journal=journal)

    def close(self) -> None:
        for store in self.stores:
            store.close()


@pytest.fixture
def host(tmp_path: Path) -> Any:
    made: list[Host] = []

    def factory(workflow: WorkflowManifest | None = None) -> Host:
        built = Host(tmp_path, workflow if workflow is not None else flow())
        made.append(built)
        return built

    yield factory
    for built in made:
        built.close()


def run(engine: WorkflowEngine, flow_manifest: WorkflowManifest, **kwargs: Any) -> Any:
    return asyncio.run(
        engine.execute(
            context(), flow_manifest.metadata.identity, {"count": 1}, timeout_seconds=10, **kwargs
        )
    )


def test_a_journalled_run_records_its_evidence(host: Any) -> None:
    built = host()
    engine = built.restart()
    result = run(engine, built.workflow)
    assert result.run.status == "succeeded" and result.run.completed_steps == 2
    entry = engine.inspect_journal(context(), result.run.run_id)
    assert entry is not None
    assert entry.plan.status == "succeeded" and entry.plan.next_step is None
    assert [s.state for s in entry.plan.steps] == ["completed", "completed"]
    assert entry.suspended_by is None
    # The evidence outlives the process that wrote it.
    assert built.restart().inspect_journal(context(), result.run.run_id) == entry


def test_an_engine_without_a_journal_is_unchanged(host: Any) -> None:
    built = host()
    installed = InstalledCapabilities()
    installed.register(
        spec(), Handler(), Input, Output, ExecutionDependencies(central_required=False)
    )
    workflows = InstalledWorkflows()
    workflows.register(built.workflow)
    engine = WorkflowEngine(workflows, BridgeExecutor(installed, LocalPolicy((grant(),))))
    result = run(engine, built.workflow)
    assert result.run.status == "succeeded"
    assert engine.inspect_journal(context(), result.run.run_id) is None
    assert engine.suspend(context(), result.run.run_id, confirmation()) is None
    assert asyncio.run(engine.recover(context(), result.run.run_id)) is None


def test_a_failed_step_leaves_it_uncertain_and_the_rest_never_started(host: Any) -> None:
    built = host(flow(3))
    engine = built.restart(FailOnce())
    result = run(engine, built.workflow)
    assert result.run.status == "failed"
    entry = engine.inspect_journal(context(), result.run.run_id)
    assert entry is not None
    assert [s.state for s in entry.plan.steps] == ["uncertain", "never_started", "never_started"]
    assert entry.plan.next_step == 0


def test_suspension_needs_a_human_and_a_dead_process(host: Any) -> None:
    built = host()
    engine = built.restart(FailOnce())
    result = run(engine, built.workflow)
    run_id = result.run.run_id
    for invalid in ({"process_confirmed_stopped": False}, {"operator": "not a symbol!"}):
        with pytest.raises(ValidationError):
            confirmation(**invalid)
    entry = engine.suspend(context(), run_id, confirmation())
    assert entry is not None and entry.suspended_by == "leo"
    assert entry.plan.status == "needs_input"
    # Suspending twice is not a transition the store allows.
    with pytest.raises(CheckpointStoreError, match="invalid_transition"):
        engine.suspend(context(), run_id, confirmation())


def test_a_live_run_cannot_be_suspended(host: Any) -> None:
    async def scenario() -> None:
        built = host()
        engine = built.restart(Stuck())
        started = await engine.execute(
            context(), built.workflow.metadata.identity, {"count": 1}, timeout_seconds=0.01
        )
        # The caller stopped waiting, but the run is alive in this process.
        with pytest.raises(CheckpointStoreError, match="invalid_transition"):
            engine.suspend(context(), started.run.run_id, confirmation())
        engine._tasks[started.run.run_id].cancel()
        await engine.wait(started.run.run_id)
        assert engine.suspend(context(), started.run.run_id, confirmation()) is not None

    asyncio.run(scenario())


def test_a_new_process_continues_a_suspended_run(host: Any) -> None:
    built = host(flow(3))
    first = built.restart(FailOnce())
    result = run(first, built.workflow)
    run_id = result.run.run_id
    assert result.run.status == "failed" and built.handler.calls == [context()]

    # A new engine: nothing in memory, only the durable journal.
    second = built.restart()
    assert second.get(run_id) is None
    second.suspend(context(), run_id, confirmation())
    recovered = asyncio.run(
        second.recover(context(), run_id, ResumePolicy(uncertain="replay_read_only"))
    )
    assert recovered is not None
    assert recovered.run.status == "succeeded"
    assert recovered.run.completed_steps == 3
    assert recovered.run.resumed_from == run_id
    assert recovered.log[0] == f"recover run {run_id} from step 1"
    # Chaining still works: each step consumed the previous step's result.
    assert [r.data for r in recovered.step_results] == [{"count": 2}, {"count": 3}, {"count": 4}]


def test_recovery_restores_a_completed_prefix_without_repeating_it(host: Any) -> None:
    built = host(flow(3))

    class FailOnSecond(Handler):
        async def __call__(self, ctx: RequestContext, inputs: Contract) -> Contract:
            if len(self.calls) == 1:
                self.calls.append(ctx)
                raise RuntimeError("private error payload")
            return await super().__call__(ctx, inputs)

    first = built.restart(FailOnSecond())
    result = run(first, built.workflow)
    assert result.run.status == "failed" and result.run.completed_steps == 1

    second = built.restart(Handler())
    second.suspend(context(), result.run.run_id, confirmation())
    recovered = asyncio.run(
        second.recover(context(), result.run.run_id, ResumePolicy(uncertain="replay_read_only"))
    )
    assert recovered is not None and recovered.run.status == "succeeded"
    # Step 1 was restored from its payload, not re-run: only steps 2 and 3 ran here.
    binding = second.bridge.installed.get(spec().identity)
    assert binding is not None and len(binding.handler.calls) == 2
    assert [r.data for r in recovered.step_results] == [{"count": 2}, {"count": 3}, {"count": 4}]


def test_recovery_refuses_what_it_cannot_justify(host: Any) -> None:
    built = host()
    engine = built.restart(FailOnce())
    result = run(engine, built.workflow)
    run_id = result.run.run_id

    # Not suspended yet: a human has not confirmed the owning process is gone.
    not_suspended = asyncio.run(engine.recover(context(), run_id))
    assert not_suspended is not None and not_suspended.run.failure is not None
    assert not_suspended.run.failure.code == "run_not_suspended"

    engine.suspend(context(), run_id, confirmation())
    # The default policy never replays an uncertain effect.
    rejected = asyncio.run(engine.recover(context(), run_id))
    assert rejected is not None and rejected.run.failure is not None
    assert rejected.run.failure.code == "uncertain_side_effect"

    # Authorization is checked again, now, not when the run started.
    denied_engine = built.restart(granted=False)
    denied = asyncio.run(
        denied_engine.recover(context(), run_id, ResumePolicy(uncertain="replay_read_only"))
    )
    assert denied is not None and denied.run.failure is not None
    assert denied.run.failure.code == "permission_denied"

    assert asyncio.run(engine.recover(context(), "run-unknown")) is None


def test_a_changed_manifest_is_a_new_decision(host: Any) -> None:
    built = host()
    engine = built.restart(FailOnce())
    result = run(engine, built.workflow)
    engine.suspend(context(), result.run.run_id, confirmation())

    # The same version, reinstalled with a different definition: provenance says no.
    changed = WorkflowManifest.model_validate(
        {**built.workflow.model_dump(), "description": "changed since the run"}
    )
    built.workflow = changed
    other = built.restart()
    refused = asyncio.run(
        other.recover(context(), result.run.run_id, ResumePolicy(uncertain="replay_read_only"))
    )
    assert refused is not None and refused.run.failure is not None
    assert refused.run.failure.code == "manifest_changed"


def test_a_key_that_already_names_a_durable_run_conflicts(host: Any) -> None:
    built = host()
    first = built.restart()
    original = run(first, built.workflow, idempotency_key="release-1")
    assert original.run.status == "succeeded"

    # A new process has no in-memory keys, but the journal remembers.
    second = built.restart()
    duplicate = run(second, built.workflow, idempotency_key="release-1")
    assert duplicate.run.status == "needs_input"
    assert duplicate.run.failure is not None
    assert duplicate.run.failure.code == "idempotency_conflict"
    assert second.get(duplicate.run.run_id) is None


class RefusingStore(SqliteCheckpointStore):
    """Refuses the write the coordinator makes before dispatching a step."""

    def replace(self, checkpoint: Any, *, expected_revision: int) -> Any:
        if any(s.state == "started" for s in checkpoint.steps):
            raise CheckpointStoreError("unavailable")
        return super().replace(checkpoint, expected_revision=expected_revision)


def test_a_step_is_not_dispatched_without_its_acknowledgment(tmp_path: Path) -> None:
    workflow = flow(1)
    handler = Handler()
    installed = InstalledCapabilities()
    installed.register(
        spec(), handler, Input, Output, ExecutionDependencies(central_required=False)
    )
    workflows = InstalledWorkflows()
    workflows.register(workflow)
    store = RefusingStore(tmp_path / "checkpoints.sqlite")
    engine = WorkflowEngine(
        workflows,
        BridgeExecutor(installed, LocalPolicy((grant(),))),
        journal=RunJournal(store, FilePayloadStore(tmp_path / "payloads")),
    )
    try:
        result = run(engine, workflow)
        assert result.run.status == "failed"
        assert result.run.failure is not None
        assert result.run.failure.code == "checkpoint_unavailable"
        # The handler never ran, and the evidence agrees.
        assert handler.calls == []
        entry = engine.inspect_journal(context(), result.run.run_id)
        assert entry is not None and entry.plan.steps[0].state == "never_started"
    finally:
        store.close()


def test_a_journal_that_cannot_start_a_run_starts_no_run(tmp_path: Path) -> None:
    class RefusingCreate(SqliteCheckpointStore):
        def create(self, checkpoint: Any) -> Any:
            raise CheckpointStoreError("capacity")

    workflow = flow(1)
    handler = Handler()
    installed = InstalledCapabilities()
    installed.register(
        spec(), handler, Input, Output, ExecutionDependencies(central_required=False)
    )
    workflows = InstalledWorkflows()
    workflows.register(workflow)
    store = RefusingCreate(tmp_path / "checkpoints.sqlite")
    engine = WorkflowEngine(
        workflows,
        BridgeExecutor(installed, LocalPolicy((grant(),))),
        journal=RunJournal(store, FilePayloadStore(tmp_path / "payloads")),
    )
    try:
        result = run(engine, workflow)
        assert result.run.status == "unavailable"
        assert result.run.failure is not None
        assert result.run.failure.code == "checkpoint_capacity"
        assert handler.calls == []
        assert engine.get(result.run.run_id) is None
    finally:
        store.close()
