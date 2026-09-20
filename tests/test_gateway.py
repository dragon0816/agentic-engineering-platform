import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_routing import FakeModel

from agent.gateway import Gateway, GatewayResult
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.evaluation import EvaluationCase
from common.execution import RequestContext, TraceIdentifiers
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

ROOT = Path(__file__).resolve().parents[1]


class Probe(Contract):
    """Raw dot-command arguments are accepted only when the input contract declares them."""

    args: str = ""


class Report(Contract):
    validated: bool = True


class Handler:
    def __init__(self) -> None:
        self.calls = 0

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        self.calls += 1
        return Report()


def capability_spec() -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": {
                "namespace": "engineering",
                "name": "validate-release",
                "version": "1.0.0",
            },
            "name": "engineering.validate_release",
            "description": "Inert release validation fixture",
            "input_contract": "engineering.validate-release.input.v1",
            "output_contract": "engineering.validate-release.output.v1",
            "side_effect": "read",
            "policy": {
                "required_permissions": ["engineering.validate"],
                "policy_refs": ["release-policy"],
            },
        }
    )


def workflow_manifest() -> WorkflowManifest:
    return WorkflowManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "release-validation",
                    "version": "1.0.0",
                },
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "private",
                "lifecycle": "draft",
            },
            "kind": "workflow",
            "description": "Inert single-step release validation workflow",
            "execution": {"mode": "local"},
            "dependencies": {"central_required": False},
            "input_contract": "engineering.validate-release.input.v1",
            "output_contract": "engineering.validate-release.output.v1",
            "steps": [{"namespace": "engineering", "name": "validate-release", "version": "1.0.0"}],
        }
    )


def request(message: str) -> RequestContext:
    return RequestContext(
        trace=TraceIdentifiers(trace_id="trace-1", request_id="request-1", span_id="span-1"),
        actor="engineer",
        namespace="engineering",
        channel="test",
        message=message,
    )


def gateway(handler: Handler, model: FakeModel | None = None, *, granted: bool = True) -> Gateway:
    skills = SkillRegistry()
    for data in json.loads((ROOT / "skills/release-workflow.json").read_text(encoding="utf-8")):
        skills.register(SkillManifest.model_validate(data))
    installed = InstalledCapabilities()
    installed.register(
        capability_spec(), handler, Probe, Report, ExecutionDependencies(central_required=False)
    )
    grants = (
        (
            CapabilityGrant.model_validate(
                {
                    "actor": "engineer",
                    "asset": capability_spec().identity,
                    "permissions": ["engineering.validate"],
                    "policy_refs": ["release-policy"],
                    "approval_ref": "release-approval",
                }
            ),
        )
        if granted
        else ()
    )
    bridge = BridgeExecutor(installed, LocalPolicy(grants))
    workflows = InstalledWorkflows()
    workflows.register(workflow_manifest())
    router = RequestRouter(CommandRouter(skills), model=model)
    return Gateway(router, bridge, WorkflowEngine(workflows, bridge))


def test_phase3_evaluation_cases_trigger_workflows_without_model() -> None:
    cases = json.loads(
        (ROOT / "evaluation/cases/phase3-workflow-trigger.json").read_text(encoding="utf-8")
    )
    assert cases
    for payload in cases:
        case = EvaluationCase.model_validate(payload)
        handler = Handler()
        model = FakeModel()
        result = asyncio.run(gateway(handler, model).handle(case.request))
        assert result.routing.decision == case.expected_route
        assert result.routing.origin == "deterministic"
        assert model.calls == []
        assert capability_spec().side_effect not in case.forbidden_side_effects
        assert result.capability is None
        assert result.workflow is not None
        assert result.workflow.run.status == "succeeded"
        assert result.workflow.run.completed_steps == 1
        assert handler.calls == 1


def test_capability_route_dispatches_through_the_bridge() -> None:
    handler = Handler()
    result = asyncio.run(gateway(handler).handle(request("release.check")))
    assert result.routing.decision.kind == "capability"
    assert result.workflow is None
    assert result.capability is not None
    assert result.capability.status == "succeeded"
    assert result.capability.data == {"validated": True}
    assert handler.calls == 1


def test_needs_input_passes_through_without_execution() -> None:
    handler = Handler()
    result = asyncio.run(gateway(handler).handle(request("completely unrelated text")))
    assert result.routing.decision.kind == "needs_input"
    assert result.capability is None and result.workflow is None
    assert handler.calls == 0


def test_model_selected_workflow_uses_the_same_contract() -> None:
    handler = Handler()
    target = workflow_manifest().metadata.identity
    model = FakeModel({"kind": "workflow", "target": target.model_dump(), "arguments": {}})
    result = asyncio.run(gateway(handler, model).handle(request("幫我把這版驗證完發出去")))
    assert result.routing.origin == "model"
    assert len(model.calls) == 1
    assert result.workflow is not None
    assert result.workflow.run.status == "succeeded"
    assert handler.calls == 1


def test_gateway_adds_no_authority() -> None:
    handler = Handler()
    result = asyncio.run(gateway(handler, granted=False).handle(request("release.package")))
    assert result.workflow is not None
    assert result.workflow.run.status == "failed"
    assert result.workflow.run.failure is not None
    assert result.workflow.run.failure.code == "permission_denied"
    assert handler.calls == 0


def test_gateway_result_cannot_misreport_execution() -> None:
    handler = Handler()
    resolved = asyncio.run(gateway(handler).handle(request("release.package")))
    with pytest.raises(ValidationError):
        GatewayResult(routing=resolved.routing)
    unresolved = asyncio.run(gateway(handler).handle(request("unrelated")))
    with pytest.raises(ValidationError):
        GatewayResult(routing=unresolved.routing, workflow=resolved.workflow)


def test_route_arguments_pass_through_unchanged() -> None:
    class Echo(Handler):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[Any] = []

        async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
            self.seen.append(inputs)
            return await super().__call__(context, inputs)

    handler = Echo()
    result = asyncio.run(gateway(handler).handle(request("release.check  notes.txt now ")))
    assert result.capability is not None and result.capability.status == "succeeded"
    assert handler.seen == [Probe(args="notes.txt now")]
    no_args = asyncio.run(gateway(handler).handle(request("release.check")))
    assert no_args.capability is not None and no_args.capability.status == "succeeded"
    assert handler.seen[-1] == Probe()
