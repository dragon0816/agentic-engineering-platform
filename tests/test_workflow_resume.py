"""Bounded in-memory resumption: completed steps are never repeated, uncertain effects
are replayed only under an explicit policy, and every replayed step is re-authorized."""

import asyncio
from typing import Any

import pytest
from pydantic import ValidationError
from test_dispatch import Handler, Input, Output, grant, spec
from test_engine import context, manifest
from test_workflow_inputs import flow_for, runner_for, step

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import (
    CapabilityGrant,
    InstalledCapabilities,
    LocalPolicy,
    TransientCapabilityError,
)
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.execution import RequestContext, ResumePlan, ResumePolicy, TraceIdentifiers
from workflow.dispatch import BridgeExecutor
from workflow.engine import MAX_RUNS_KEPT, InstalledWorkflows, WorkflowEngine


class FailOn(Handler):
    """Raise an unknown error on the given call numbers; succeed otherwise."""

    def __init__(self, *failing_calls: int) -> None:
        super().__init__()
        self.failing_calls = set(failing_calls)
        self.count = 0

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.count += 1
        if self.count in self.failing_calls:
            raise RuntimeError("private error payload")
        return await super().__call__(context, inputs)


class Slow(Handler):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        await asyncio.sleep(30)
        return await super().__call__(context, inputs)


def write_spec() -> CapabilitySpec:
    data = spec().model_dump()
    data["identity"]["name"] = "write-count"
    data["name"] = "sample.write_count"
    data["side_effect"] = "write"
    return CapabilitySpec.model_validate(data)


def write_grant() -> CapabilityGrant:
    return CapabilityGrant.model_validate(
        {**grant().model_dump(), "asset": write_spec().identity.model_dump()}
    )


def mixed_engine(
    read_handler: Handler, write_handler: Handler
) -> tuple[WorkflowEngine, WorkflowManifest]:
    installed = InstalledCapabilities()
    deps = ExecutionDependencies(central_required=False)
    installed.register(spec(), read_handler, Input, Output, deps)
    installed.register(write_spec(), write_handler, Input, Output, deps)
    bridge = BridgeExecutor(installed, LocalPolicy((grant(), write_grant())))
    workflows = InstalledWorkflows()
    flow = manifest([spec().identity, write_spec().identity, spec().identity])
    workflows.register(flow)
    return WorkflowEngine(workflows, bridge), flow


def run(runner: WorkflowEngine, flow: WorkflowManifest, **kwargs: Any) -> Any:
    return asyncio.run(
        runner.execute(
            context(), flow.metadata.identity, {"count": 1}, timeout_seconds=10, **kwargs
        )
    )


def resume(runner: WorkflowEngine, run_id: str, **kwargs: Any) -> Any:
    return asyncio.run(runner.resume(context(), run_id, timeout_seconds=10, **kwargs))


@pytest.mark.parametrize("data", [{"uncertain": "replay"}, {"uncertain": True}, {"replay": 1}])
def test_invalid_resume_policy(data: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ResumePolicy.model_validate(data)


def test_resume_plan_contract_requires_linear_progress() -> None:
    base = {
        "run_id": "run-1",
        "workflow": spec().identity.model_dump(),
        "status": "failed",
        "steps": [
            {"step_index": 0, "state": "completed"},
            {"step_index": 1, "state": "uncertain", "code": "handler_error"},
        ],
    }
    assert ResumePlan.model_validate({**base, "next_step": 1}).next_step == 1
    with pytest.raises(ValidationError):
        ResumePlan.model_validate({**base, "next_step": 0})
    with pytest.raises(ValidationError):
        ResumePlan.model_validate({**base, "next_step": None})
    with pytest.raises(ValidationError):
        ResumePlan.model_validate(
            {**base, "steps": [{"step_index": 0, "state": "completed", "code": "x"}]}
        )


def test_inspect_classifies_completed_uncertain_and_never_started() -> None:
    handler = FailOn(2)
    flow = flow_for([spec().identity.model_dump()] * 3)
    runner = runner_for(flow, handler)
    result = run(runner, flow)
    assert result.run.status == "failed" and result.run.failure.code == "handler_error"
    plan = runner.inspect(context(), result.run.run_id)
    assert plan is not None
    assert [(s.state, s.code) for s in plan.steps] == [
        ("completed", None),
        ("uncertain", "handler_error"),
        ("never_started", None),
    ]
    assert plan.next_step == 1
    assert runner.inspect(context(), "run-missing") is None


def test_denied_step_had_no_effect_and_resumes_after_a_grant() -> None:
    handler = Handler()
    installed = InstalledCapabilities()
    installed.register(
        spec(), handler, Input, Output, ExecutionDependencies(central_required=False)
    )
    bridge = BridgeExecutor(installed, LocalPolicy(()))
    workflows = InstalledWorkflows()
    flow = manifest([spec().identity] * 2)
    workflows.register(flow)
    runner = WorkflowEngine(workflows, bridge)
    denied = run(runner, flow)
    assert denied.run.failure.code == "permission_denied"
    plan = runner.inspect(context(), denied.run.run_id)
    assert plan is not None
    assert [s.state for s in plan.steps] == ["never_started", "never_started"]
    assert plan.steps[0].code == "permission_denied"
    # Still denied: the plan grants nothing, and no run record is created.
    still = resume(runner, denied.run.run_id)
    assert still is not None and still.run.failure.code == "permission_denied"
    assert runner.get(still.run.run_id) is None
    bridge.policy = LocalPolicy((grant(),))
    resumed = resume(runner, denied.run.run_id)
    assert resumed is not None and resumed.run.status == "succeeded"
    assert resumed.run.completed_steps == 2 and resumed.run.resumed_from == denied.run.run_id
    assert len(handler.calls) == 2


def test_uncertain_effect_is_rejected_without_an_explicit_policy() -> None:
    handler = FailOn(2)
    runner = runner_for(flow_for([spec().identity.model_dump()] * 3), handler)
    flow = flow_for([spec().identity.model_dump()] * 3)
    failed = run(runner, flow)
    rejected = resume(runner, failed.run.run_id)
    assert rejected is not None
    assert rejected.run.status == "needs_input"
    assert rejected.run.failure.code == "uncertain_side_effect"
    assert runner.get(rejected.run.run_id) is None
    assert handler.count == 2


def test_replay_read_only_resumes_reads_but_not_writes() -> None:
    read = FailOn()
    writer = FailOn(1)
    runner, flow = mixed_engine(read, writer)
    # Step 2 is the write capability; its handler failed once, effect uncertain.
    failed = run(runner, flow)
    assert failed.run.completed_steps == 1 and failed.run.failure.code == "handler_error"
    rejected = resume(runner, failed.run.run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    assert rejected is not None and rejected.run.failure.code == "uncertain_side_effect"
    assert writer.count == 1
    accepted = resume(
        runner, failed.run.run_id, policy=ResumePolicy(uncertain="replay_side_effects")
    )
    assert accepted is not None and accepted.run.status == "succeeded"
    assert accepted.run.completed_steps == 3
    assert writer.count == 2
    # Step 1 (read, completed) was never repeated; step 3 ran once after the resume.
    assert read.count == 2


def test_completed_results_feed_later_inputs_without_re_running() -> None:
    handler = FailOn(2)
    flow = flow_for(
        [
            spec().identity.model_dump(),
            step({"source": "step", "step_index": 0, "path": ["count"]}),
        ]
    )
    runner = runner_for(flow, handler)
    failed = run(runner, flow)
    assert failed.run.completed_steps == 1
    resumed = resume(runner, failed.run.run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    assert resumed is not None and resumed.run.status == "succeeded"
    assert [r.data for r in resumed.step_results] == [{"count": 2}, {"count": 3}]
    assert handler.count == 3
    assert resumed.log[0] == f"resume run {failed.run.run_id} from step 2"
    # The original run is immutable history.
    assert runner.get(failed.run.run_id) == failed


def test_resumed_runs_can_be_resumed_again() -> None:
    handler = FailOn(2, 3)
    flow = flow_for([spec().identity.model_dump()] * 2)
    runner = runner_for(flow, handler)
    first = run(runner, flow)
    second = resume(runner, first.run.run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    assert second is not None and second.run.status == "failed"
    assert second.run.resumed_from == first.run.run_id
    third = resume(runner, second.run.run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    assert third is not None and third.run.status == "succeeded"
    assert third.run.resumed_from == second.run.run_id
    assert handler.count == 4


def test_cancelled_run_leaves_the_interrupted_step_uncertain() -> None:
    async def scenario() -> None:
        flow = flow_for([spec().identity.model_dump()] * 2)
        runner = runner_for(flow, Slow())
        snapshot = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, timeout_seconds=0.01
        )
        active = await runner.resume(context(), snapshot.run.run_id)
        assert active is not None and active.run.failure is not None
        assert active.run.failure.code == "run_active"
        runner._tasks[snapshot.run.run_id].cancel()
        final = await runner.wait(snapshot.run.run_id)
        assert final is not None and final.run.failure is not None
        assert final.run.failure.code == "workflow_aborted"
        plan = runner.inspect(context(), snapshot.run.run_id)
        assert plan is not None
        assert plan.steps[0].state == "uncertain" and plan.steps[0].code == "workflow_aborted"
        rejected = await runner.resume(context(), snapshot.run.run_id)
        assert rejected is not None and rejected.run.failure is not None
        assert rejected.run.failure.code == "uncertain_side_effect"

    asyncio.run(scenario())


def test_missing_run_input_is_never_started() -> None:
    flow = flow_for([step({"source": "run", "path": ["absent"]})])
    runner = runner_for(flow)
    rejected = run(runner, flow)
    assert rejected.run.failure.code == "workflow_input_missing"
    assert runner.inspect(context(), rejected.run.run_id) is None  # preflight: no run existed


def test_complete_unknown_evicted_and_foreign_runs_cannot_resume() -> None:
    flow = flow_for([spec().identity.model_dump()])
    runner = runner_for(flow)
    done = run(runner, flow)
    complete = resume(runner, done.run.run_id)
    assert complete is not None and complete.run.failure.code == "run_complete"
    assert resume(runner, "run-missing") is None
    other = RequestContext(
        trace=TraceIdentifiers(trace_id="trace-2", request_id="request-2", span_id="span-2"),
        actor="someone-else",
        namespace="sample",
        channel="test",
        message="resume",
    )
    # Another actor cannot tell the run apart from an unknown one.
    assert asyncio.run(runner.resume(other, done.run.run_id)) is None
    assert runner.inspect(other, done.run.run_id) is None
    for _ in range(MAX_RUNS_KEPT):
        run(runner, flow)
    assert resume(runner, done.run.run_id) is None


def test_resume_does_not_consult_or_consume_idempotency_keys() -> None:
    handler = FailOn(1)
    flow = flow_for([spec().identity.model_dump()])
    runner = runner_for(flow, handler)
    failed = run(runner, flow, idempotency_key="release-1")
    resumed = resume(runner, failed.run.run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    assert resumed is not None and resumed.run.status == "succeeded"
    replay = run(runner, flow, idempotency_key="release-1")
    assert replay.run.run_id == failed.run.run_id and replay.run.status == "failed"
    assert handler.count == 2


class TransientOnce(Handler):
    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.count += 1
        if self.count == 1:
            raise TransientCapabilityError("private error payload")
        return await super().__call__(context, inputs)


def test_a_run_can_be_continued_only_once() -> None:
    writer = FailOn()
    runner, flow = mixed_engine(FailOn(), writer)
    runner.bridge.policy = LocalPolicy(())
    denied = run(runner, flow)
    assert denied.run.failure.code == "permission_denied"
    runner.bridge.policy = LocalPolicy((grant(), write_grant()))
    first = resume(runner, denied.run.run_id)
    assert first is not None and first.run.status == "succeeded"
    assert writer.count == 1
    again = resume(runner, denied.run.run_id)
    assert again is not None and again.run.status == "needs_input"
    assert again.run.failure.code == "already_resumed"
    assert writer.count == 1
    assert runner.get(again.run.run_id) is None


def test_missing_prior_result_path_is_rejected_before_a_run_exists() -> None:
    flow = flow_for(
        [
            spec().identity.model_dump(),
            step({"source": "step", "step_index": 0, "path": ["missing"]}),
        ]
    )
    runner = runner_for(flow)
    failed = run(runner, flow)
    assert failed.run.failure.code == "workflow_input_missing"
    assert failed.run.completed_steps == 1
    plan = runner.inspect(context(), failed.run.run_id)
    assert plan is not None and plan.steps[1].state == "never_started"
    kept = len(runner._runs)
    rejected = resume(runner, failed.run.run_id)
    assert rejected is not None and rejected.run.status == "needs_input"
    assert rejected.run.failure.code == "workflow_input_missing"
    assert len(runner._runs) == kept


def test_inspect_reports_a_live_run_as_running() -> None:
    async def scenario() -> None:
        flow = flow_for([spec().identity.model_dump()])
        runner = runner_for(flow, Slow())
        snapshot = await runner.execute(
            context(), flow.metadata.identity, {"count": 1}, timeout_seconds=0.01
        )
        assert snapshot.run.failure is not None
        assert snapshot.run.failure.code == "workflow_timeout"
        plan = runner.inspect(context(), snapshot.run.run_id)
        assert plan is not None and plan.status == "running"
        assert plan.steps[0].state == "uncertain" and plan.steps[0].code is None
        runner._tasks[snapshot.run.run_id].cancel()
        await runner.wait(snapshot.run.run_id)

    asyncio.run(scenario())


def test_handler_evidence_survives_a_later_pre_handler_rejection() -> None:
    async def scenario() -> None:
        data = step({"source": "run", "path": ["count"]})
        data["retry"] = {"max_attempts": 2, "delay_ms": 200}
        flow = flow_for([data])
        handler = TransientOnce()
        runner = runner_for(flow, handler)
        task = asyncio.create_task(
            runner.execute(context(), flow.metadata.identity, {"count": 1}, timeout_seconds=10)
        )
        await asyncio.sleep(0.02)
        # Revoked during the retry delay: attempt 2 is denied before any handler,
        # but attempt 1 already ran, so the step's effect is uncertain.
        runner.bridge.policy = LocalPolicy(())
        result = await task
        assert result.run.failure is not None
        assert result.run.failure.code == "permission_denied"
        assert handler.count == 1
        plan = runner.inspect(context(), result.run.run_id)
        assert plan is not None
        assert plan.steps[0].state == "uncertain" and plan.steps[0].code == "permission_denied"
        assert [a.handler_invoked for a in result.attempts] == [True, False]

    asyncio.run(scenario())
