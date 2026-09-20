import asyncio
from typing import Any

import pytest
from test_dispatch import Handler, Input, Output, grant, spec

from capabilities.runtime import InstalledCapabilities, LocalPolicy
from common.assets import AssetIdentity, ExecutionDependencies, WorkflowManifest
from common.execution import RequestContext, TraceIdentifiers
from workflow.dispatch import BridgeExecutor
from workflow.engine import (
    MAX_LOG_LINES,
    MAX_RUNS_KEPT,
    InstalledWorkflows,
    WorkflowEngine,
    _RunRecord,
)


def manifest(steps: list[AssetIdentity], **changes: Any) -> WorkflowManifest:
    data: dict[str, Any] = {
        "metadata": {
            "identity": {"namespace": "sample", "name": "count-twice", "version": "1.0.0"},
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "private",
            "lifecycle": "draft",
        },
        "kind": "workflow",
        "description": "Inert two-step count fixture",
        "execution": {"mode": "local"},
        "dependencies": {"central_required": False},
        "input_contract": "count.input.v1",
        "output_contract": "count.output.v1",
        "steps": [step.model_dump() for step in steps],
        **changes,
    }
    return WorkflowManifest.model_validate(data)


def context() -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
        actor="engineer",
        namespace="sample",
        channel="test",
        message="run the workflow",
    )


def engine(
    handler: Handler | None = None,
    *,
    steps: int = 2,
    granted: bool = True,
    install_capability: bool = True,
) -> tuple[WorkflowEngine, WorkflowManifest]:
    installed = InstalledCapabilities()
    if install_capability:
        installed.register(
            spec(),
            handler if handler is not None else Handler(),
            Input,
            Output,
            ExecutionDependencies(central_required=False),
        )
    bridge = BridgeExecutor(installed, LocalPolicy((grant(),) if granted else ()))
    workflows = InstalledWorkflows()
    flow = manifest([spec().identity] * steps)
    workflows.register(flow)
    return WorkflowEngine(workflows, bridge), flow


def test_sequential_steps_dispatch_through_bridge_policy() -> None:
    handler = Handler()
    runner, flow = engine(handler)
    snapshot = asyncio.run(
        runner.execute(context(), flow.metadata.identity, {"count": 1}, timeout_seconds=10)
    )
    assert snapshot.run.status == "succeeded"
    assert snapshot.run.completed_steps == 2
    assert len(handler.calls) == 2
    assert [result.status for result in snapshot.step_results] == ["succeeded", "succeeded"]
    assert snapshot.log[0] == "start workflow sample/count-twice@1.0.0"
    assert snapshot.log[1] == "step 1 sample/count@1.0.0 succeeded"
    assert snapshot.log[-1] == "workflow succeeded"
    assert runner.get(snapshot.run.run_id) == snapshot


def test_uninstalled_workflow_leaves_no_ghost_run() -> None:
    runner, _ = engine()
    missing = AssetIdentity(namespace="sample", name="absent", version="1.0.0")
    snapshot = asyncio.run(runner.execute(context(), missing, timeout_seconds=10))
    assert snapshot.run.status == "unavailable"
    assert snapshot.run.failure is not None
    assert snapshot.run.failure.code == "workflow_not_installed"
    assert runner.get(snapshot.run.run_id) is None


def test_secret_requirements_fail_before_a_run_exists() -> None:
    runner, _ = engine()
    flow = manifest(
        [spec().identity],
        metadata={
            "identity": {"namespace": "sample", "name": "secretive", "version": "1.0.0"},
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "private",
            "lifecycle": "draft",
        },
        secrets=[{"name": "github_token"}],
    )
    runner.workflows.register(flow)
    snapshot = asyncio.run(runner.execute(context(), flow.metadata.identity, timeout_seconds=10))
    assert snapshot.run.status == "unavailable"
    assert snapshot.run.failure is not None
    assert snapshot.run.failure.code == "secret_resolution_unavailable"
    assert runner.get(snapshot.run.run_id) is None


def test_denied_step_ends_the_run_with_its_code() -> None:
    handler = Handler()
    runner, flow = engine(handler, granted=False)
    snapshot = asyncio.run(
        runner.execute(context(), flow.metadata.identity, {"count": 1}, timeout_seconds=10)
    )
    assert snapshot.run.status == "failed"
    assert snapshot.run.failure is not None
    assert snapshot.run.failure.code == "permission_denied"
    assert snapshot.run.completed_steps == 0
    assert handler.calls == []


def test_missing_step_capability_is_unavailable() -> None:
    runner, flow = engine(install_capability=False)
    snapshot = asyncio.run(
        runner.execute(context(), flow.metadata.identity, {"count": 1}, timeout_seconds=10)
    )
    assert snapshot.run.status == "unavailable"
    assert snapshot.run.failure is not None
    assert snapshot.run.failure.code == "capability_not_installed"


def test_caller_wait_timeout_is_not_the_final_state() -> None:
    class Slow(Handler):
        async def __call__(self, context: RequestContext, inputs: Any) -> Any:
            await asyncio.sleep(0.2)
            return await super().__call__(context, inputs)

    async def scenario() -> None:
        runner, flow = engine(Slow(), steps=1)
        snapshot = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, timeout_seconds=0.01
        )
        assert snapshot.run.status == "failed"
        assert snapshot.run.failure is not None
        assert snapshot.run.failure.code == "workflow_timeout"
        final = await runner.wait(snapshot.run.run_id)
        assert final is not None
        assert final.run.status == "succeeded"
        assert final.run.completed_steps == 1

    asyncio.run(scenario())


def test_only_the_last_runs_are_kept() -> None:
    async def scenario() -> None:
        runner, flow = engine(steps=1)
        first = await runner.execute(context(), flow.metadata.identity, {"count": 1})
        last = first
        for _ in range(MAX_RUNS_KEPT):
            last = await runner.execute(context(), flow.metadata.identity, {"count": 1})
        assert runner.get(first.run.run_id) is None
        assert runner.get(last.run.run_id) is not None

    asyncio.run(scenario())


def test_log_is_capped_with_one_truncation_marker() -> None:
    record = _RunRecord(spec().identity, context().trace)
    for n in range(MAX_LOG_LINES + 5):
        record.append_log(f"line-{n}")
    assert len(record.log) == MAX_LOG_LINES + 1
    assert record.log[-1] == f"… log truncated ({MAX_LOG_LINES} lines)"


def test_logs_never_contain_arguments_or_payloads() -> None:
    runner, flow = engine()
    snapshot = asyncio.run(
        runner.execute(context(), flow.metadata.identity, {"count": 41}, timeout_seconds=10)
    )
    assert snapshot.run.status == "succeeded"
    assert all("41" not in line and "42" not in line for line in snapshot.log)
    assert snapshot.step_results[0].data == {"count": 42}


def test_duplicate_workflow_versions_cannot_be_installed() -> None:
    runner, flow = engine()
    with pytest.raises(ValueError, match="already installed"):
        runner.workflows.register(flow)
