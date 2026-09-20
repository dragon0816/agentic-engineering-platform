"""Gateway integration with different contracts and per-step authorization."""

import asyncio
import json

import pytest
from test_gateway import ROOT, Handler, Report, capability_spec, gateway, request, workflow_manifest
from test_routing import FakeModel

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityGrant, LocalPolicy
from common.assets import ExecutionDependencies, WorkflowManifest
from common.base import Contract
from common.evaluation import EvaluationCase
from common.execution import RequestContext
from workflow.engine import InstalledWorkflows


class SummaryInput(Contract):
    approved: bool


class Summarize:
    def __init__(self) -> None:
        self.seen: list[SummaryInput] = []

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        assert isinstance(inputs, SummaryInput)
        self.seen.append(inputs)
        return Report(validated=inputs.approved)


@pytest.mark.parametrize("mode", ["dot", "keyword", "model", "denied"])
def test_gateway_chains_validated_outputs_under_each_steps_policy(mode: str) -> None:
    first, second = Handler(), Summarize()
    model = FakeModel(
        {
            "kind": "workflow",
            "target": workflow_manifest().metadata.identity.model_dump(),
            "arguments": {},
        }
    )
    app = gateway(first, model)
    data = capability_spec().model_dump()
    data["identity"]["name"] = "summarize"
    data["name"] = "engineering.summarize"
    data["input_contract"] = "summary.input.v1"
    summary = CapabilitySpec.model_validate(data)
    app.bridge.installed.register(
        summary, second, SummaryInput, Report, ExecutionDependencies(central_required=False)
    )
    app.bridge.policy = LocalPolicy(
        tuple(
            CapabilityGrant(
                actor="engineer",
                asset=cap.identity,
                permissions=("engineering.validate",),
                policy_refs=("release-policy",),
                approval_ref="release-approval",
            )
            for cap in ([capability_spec()] if mode == "denied" else [capability_spec(), summary])
        )
    )
    payload = workflow_manifest().model_dump(mode="json")
    payload["steps"].append(
        {
            "capability": summary.identity.model_dump(),
            "inputs": {"approved": {"source": "step", "step_index": 0, "path": ["validated"]}},
        }
    )
    app.engine.workflows = InstalledWorkflows()
    app.engine.workflows.register(WorkflowManifest.model_validate(payload))
    cases = [
        EvaluationCase.model_validate(item)
        for item in json.loads(
            (ROOT / "evaluation/cases/phase3-workflow-trigger.json").read_text(encoding="utf-8")
        )
    ]
    selected = cases[1 if mode == "keyword" else 0]
    req = request("幫我把這版驗證完發出去") if mode == "model" else selected.request
    result = asyncio.run(app.handle(req))
    assert result.workflow is not None
    assert first.calls == 1
    assert len(model.calls) == (1 if mode == "model" else 0)
    if mode != "model":
        assert result.routing.decision == selected.expected_route
        assert all(
            cap.side_effect not in selected.forbidden_side_effects
            for cap in (capability_spec(), summary)
        )
    if mode == "denied":
        assert result.workflow.run.status == "failed"
        assert result.workflow.run.failure is not None
        assert result.workflow.run.failure.code == "permission_denied"
        assert result.workflow.run.completed_steps == 1
        assert second.seen == []
    else:
        assert result.workflow.run.status == "succeeded"
        assert result.workflow.run.completed_steps == 2
        assert second.seen == [SummaryInput(approved=True)]
        assert result.workflow.step_results[-1].data == {"validated": True}
    assert all(event.trace == req.trace for event in app.bridge.events)
