"""Run control through the Gateway: inspect/resume use the engine's ownership and
authorization rules, the policy is never taken from the message or a model, and no
routed request can trigger a resumption."""

import asyncio

import pytest
from pydantic import ValidationError
from test_gateway import Handler, capability_spec, gateway, request, workflow_manifest
from test_routing import FakeModel

from agent.gateway import Gateway, RunControlResult
from capabilities.runtime import CapabilityGrant, LocalPolicy
from common.base import Contract
from common.execution import RequestContext, ResumePolicy, TraceIdentifiers


class FailOnce(Handler):
    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        if not self.calls:
            self.calls += 1
            raise RuntimeError("private error payload")
        return await super().__call__(context, inputs)


def release_grant() -> CapabilityGrant:
    return CapabilityGrant.model_validate(
        {
            "actor": "engineer",
            "asset": capability_spec().identity,
            "permissions": ["engineering.validate"],
            "policy_refs": ["release-policy"],
            "approval_ref": "release-approval",
        }
    )


def other_actor(message: str) -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="trace-2", request_id="request-2", span_id="span-2"),
        actor="someone-else",
        namespace="engineering",
        channel="test",
        message=message,
    )


def failed_release(handler: Handler | None = None) -> tuple[Gateway, str]:
    gw = gateway(handler if handler is not None else FailOnce())
    result = asyncio.run(gw.handle(request("release.package")))
    assert result.workflow is not None and result.workflow.run.status == "failed"
    assert result.workflow.run.failure is not None
    assert result.workflow.run.failure.code == "handler_error"
    return gw, result.workflow.run.run_id


def test_run_control_result_cannot_misreport_its_action() -> None:
    gw, run_id = failed_release()
    inspected = asyncio.run(gw.inspect(request("status"), run_id))
    assert inspected.plan is not None
    with pytest.raises(ValidationError):
        RunControlResult(action="resume", run_id=run_id, plan=inspected.plan)
    resumed = asyncio.run(
        gw.resume(request("go"), run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    )
    assert resumed.workflow is not None
    with pytest.raises(ValidationError):
        RunControlResult(action="inspect", run_id=run_id, workflow=resumed.workflow)
    with pytest.raises(ValidationError):
        RunControlResult(action="inspect", run_id="")


def test_inspect_then_resume_through_the_gateway() -> None:
    handler = FailOnce()
    gw, run_id = failed_release(handler)
    inspected = asyncio.run(gw.inspect(request("what happened"), run_id))
    assert inspected.action == "inspect" and inspected.workflow is None
    assert inspected.plan is not None
    assert [(s.state, s.code) for s in inspected.plan.steps] == [("uncertain", "handler_error")]
    rejected = asyncio.run(gw.resume(request("resume it"), run_id))
    assert rejected.workflow is not None and rejected.workflow.run.failure is not None
    assert rejected.workflow.run.status == "needs_input"
    assert rejected.workflow.run.failure.code == "uncertain_side_effect"
    assert handler.calls == 1
    resumed = asyncio.run(
        gw.resume(request("resume it"), run_id, policy=ResumePolicy(uncertain="replay_read_only"))
    )
    assert resumed.action == "resume" and resumed.plan is None
    assert resumed.workflow is not None and resumed.workflow.run.status == "succeeded"
    assert resumed.workflow.run.resumed_from == run_id
    assert resumed.workflow.run.trace == request("resume it").trace
    assert handler.calls == 2


def test_policy_is_never_read_from_the_message() -> None:
    gw, run_id = failed_release()
    for message in ("run.resume replay_side_effects", "replay_read_only", '{"uncertain": "x"}'):
        result = asyncio.run(gw.resume(request(message), run_id))
        assert result.workflow is not None and result.workflow.run.failure is not None
        assert result.workflow.run.failure.code == "uncertain_side_effect"


def test_gateway_resume_adds_no_authority() -> None:
    handler = Handler()
    gw = gateway(handler, granted=False)
    denied = asyncio.run(gw.handle(request("release.package")))
    assert denied.workflow is not None and denied.workflow.run.failure is not None
    assert denied.workflow.run.failure.code == "permission_denied"
    run_id = denied.workflow.run.run_id
    still = asyncio.run(gw.resume(request("again"), run_id))
    assert still.workflow is not None and still.workflow.run.failure is not None
    assert still.workflow.run.failure.code == "permission_denied"
    assert handler.calls == 0
    gw.bridge.policy = LocalPolicy((release_grant(),))
    resumed = asyncio.run(gw.resume(request("again"), run_id))
    assert resumed.workflow is not None and resumed.workflow.run.status == "succeeded"
    assert handler.calls == 1


def test_other_actors_and_unknown_runs_look_identical() -> None:
    gw, run_id = failed_release()
    for context in (other_actor("inspect"), request("inspect")):
        unknown = asyncio.run(gw.inspect(context, "run-does-not-exist"))
        assert unknown.plan is None and unknown.workflow is None
    foreign = asyncio.run(gw.inspect(other_actor("inspect"), run_id))
    assert foreign.plan is None and foreign.workflow is None
    resumed = asyncio.run(gw.resume(other_actor("resume"), run_id))
    assert resumed.plan is None and resumed.workflow is None


def test_no_routed_request_can_trigger_a_resumption() -> None:
    handler = FailOnce()
    gw, run_id = failed_release(handler)
    target = workflow_manifest().metadata.identity
    proposals = [
        {"kind": "resume", "run_id": run_id},
        {"kind": "workflow", "target": target.model_dump(), "arguments": {"run_id": run_id}},
    ]
    for proposal in proposals:
        model = FakeModel(proposal)
        gw.router.model = model
        result = asyncio.run(gw.handle(request("continue the release")))
        assert len(model.calls) == 1
        assert result.workflow is None or result.workflow.run.resumed_from is None
    # The failed run was never continued by routing; only the host can resume it.
    plan = asyncio.run(gw.inspect(request("status"), run_id)).plan
    assert plan is not None and plan.status == "failed"
    assert handler.calls == 1
