"""Product gate E2E-02: SOP -> validated deterministic Workflow."""

import asyncio
import json
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from agent.gateway import Gateway
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from capabilities.workflow_author.contracts import (
    DraftWorkflowRequest,
    WorkflowAcceptanceOutcome,
    WorkflowAcceptanceRequest,
    WorkflowDraft,
    WorkflowFixture,
    WorkflowValidationEvidence,
)
from capabilities.workflow_author.handlers import DRAFT_SPEC, DraftWorkflowHandler
from common.assets import (
    AssetIdentity,
    BusinessApproval,
    ExecutionDependencies,
)
from common.base import Contract
from common.enrollment import BridgeBinding, BridgeDevice
from common.execution import RequestContext, TraceIdentifiers
from common.local_agent import BridgeMembership, LocalAgentRequest
from host_runtime.agent import LocalAgent
from host_runtime.state import SqliteLocalState
from host_runtime.workflow_author import PersonalWorkflowAuthor, publish_validated_workflow
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

ROOT = Path(__file__).resolve().parent
FIXTURE = json.loads(
    (ROOT / "fixtures" / "e2e_02" / "sop-workflow.json").read_text(encoding="utf-8")
)
TRACE = TraceIdentifiers(trace_id="e2e02-trace", request_id="e2e02-request", span_id="e2e02-span")
NORMALIZE = AssetIdentity(namespace="demo", name="normalize-categories", version="1.0.0")
COUNT = AssetIdentity(namespace="demo", name="count-categories", version="1.0.0")


class NormalizeInput(Contract):
    records: tuple[str, ...]


class NormalizeOutput(Contract):
    categories: tuple[str, ...]


class CountInput(Contract):
    categories: tuple[str, ...]


class CountOutput(Contract):
    counts: dict[str, int]


async def normalize(context: RequestContext, inputs: Contract) -> Contract:
    item = NormalizeInput.model_validate(inputs)
    return NormalizeOutput(categories=tuple(value.strip().lower() for value in item.records))


async def count(context: RequestContext, inputs: Contract) -> Contract:
    item = CountInput.model_validate(inputs)
    return CountOutput(counts=dict(sorted(Counter(item.categories).items())))


def capability(
    identity: AssetIdentity, name: str, input_name: str, output_name: str
) -> CapabilitySpec:
    return CapabilitySpec.model_validate(
        {
            "identity": identity.model_dump(),
            "name": name,
            "description": name,
            "input_contract": input_name,
            "output_contract": output_name,
            "side_effect": "read",
            "policy": {
                "required_permissions": [f"{name}.use"],
                "policy_refs": ["e2e-02-policy"],
            },
        }
    )


NORMALIZE_SPEC = capability(
    NORMALIZE, "demo.normalize", "demo.normalize.input.v1", "demo.normalize.output.v1"
)
COUNT_SPEC = capability(COUNT, "demo.count", "demo.count.input.v1", "demo.count.output.v1")


def manifest(*, omit_count: bool = False) -> dict[str, Any]:
    steps: list[dict[str, Any]] = [
        {
            "capability": NORMALIZE.model_dump(),
            "inputs": {"records": {"source": "run", "path": ["records"]}},
        }
    ]
    if not omit_count:
        steps.append(
            {
                "capability": COUNT.model_dump(),
                "inputs": {
                    "categories": {
                        "source": "step",
                        "step_index": 0,
                        "path": ["categories"],
                    }
                },
            }
        )
    return {
        "metadata": {
            "identity": {
                "namespace": "engineering",
                "name": "category-summary",
                "version": "1.0.0",
            },
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "team",
            "lifecycle": "draft",
        },
        "kind": "workflow",
        "description": "Normalize categories and count records by category.",
        "execution": {"mode": "local"},
        "dependencies": {
            "central_required": False,
            "local_capabilities": [
                "demo.normalize",
                *([] if omit_count else ["demo.count"]),
            ],
        },
        "input_contract": "engineering.category-summary.input.v1",
        "output_contract": ("demo.normalize.output.v1" if omit_count else "demo.count.output.v1"),
        "steps": steps,
    }


class ScriptedModel:
    """Routes the user request, then supplies candidate documents in order."""

    def __init__(self, draft: DraftWorkflowRequest, *documents: dict[str, Any]) -> None:
        self.draft = draft
        self.documents = list(documents)
        self.calls: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        if request.output_contract == "platform.route-proposal.v1":
            answer: object = {
                "kind": "capability",
                "target": DRAFT_SPEC.identity.model_dump(),
                "arguments": self.draft.model_dump(mode="json"),
            }
        else:
            answer = self.documents.pop(0)
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            structured_output=answer,
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def draft_request() -> DraftWorkflowRequest:
    return DraftWorkflowRequest.model_validate(
        {
            "sop": FIXTURE["sop"],
            "namespace": FIXTURE["namespace"],
            "name": FIXTURE["name"],
            "required_capabilities": FIXTURE["required_capabilities"],
        }
    )


def skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "workflow-authoring",
                    "version": "1.0.0",
                },
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "team",
                "lifecycle": "published",
            },
            "alias": "workflow",
            "instructions": "Turn a bounded SOP into a candidate Workflow.",
            "commands": [
                {"name": "draft", "kind": "capability", "target": DRAFT_SPEC.identity.model_dump()}
            ],
        }
    )


def grant(spec: CapabilitySpec) -> CapabilityGrant:
    return CapabilityGrant(
        actor="engineer",
        asset=spec.identity,
        permissions=spec.policy.required_permissions,
        policy_refs=spec.policy.policy_refs,
        approval_ref="e2e-02-execution-approval" if spec.policy.approval_required else None,
    )


def resident(tmp_path: Path, model: ScriptedModel) -> tuple[LocalAgent, BridgeExecutor]:
    installed = InstalledCapabilities()
    installed.register(
        NORMALIZE_SPEC,
        normalize,
        NormalizeInput,
        NormalizeOutput,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        COUNT_SPEC,
        count,
        CountInput,
        CountOutput,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        DRAFT_SPEC,
        DraftWorkflowHandler(installed, model=model, model_alias="company"),
        DraftWorkflowRequest,
        WorkflowDraft,
        ExecutionDependencies(central_required=False),
    )
    bridge = BridgeExecutor(
        installed,
        LocalPolicy(tuple(grant(item) for item in (DRAFT_SPEC, NORMALIZE_SPEC, COUNT_SPEC))),
    )
    skills = SkillRegistry()
    skills.register(skill())
    gateway = Gateway(
        RequestRouter(CommandRouter(skills), model=model, model_alias="company", local_only=False),
        bridge,
        WorkflowEngine(InstalledWorkflows(), bridge),
    )
    device = BridgeDevice(
        bridge_id="bridge-company",
        registered_by="engineer",
        device_kind="company_workstation",
        windows_account_mode="dedicated_user",
        resource_scope="corporate_internal",
        local_isolation="single_user",
    )
    membership = BridgeMembership(
        device=device,
        bindings=(BridgeBinding(bridge_id=device.bridge_id, actor="engineer", role="operator"),),
    )
    state = SqliteLocalState(tmp_path / "state.sqlite", bridge_id=device.bridge_id)
    return LocalAgent(membership, gateway, state), bridge


def user_request() -> LocalAgentRequest:
    return LocalAgentRequest(
        ingress="local",
        actor="engineer",
        bridge_id="bridge-company",
        namespace="engineering",
        message=FIXTURE["sop"],
        trace=TRACE,
    )


def acceptance(expected: object | None = None) -> WorkflowAcceptanceRequest:
    return WorkflowAcceptanceRequest(
        draft=draft_request(),
        fixture=WorkflowFixture(
            arguments=FIXTURE["arguments"],
            expected_output=FIXTURE["expected_output"] if expected is None else expected,
        ),
    )


def test_e2e_02_acceptance_contract_rejects_ambiguous_or_secret_inputs() -> None:
    with pytest.raises(ValueError, match="unique scoped identities"):
        DraftWorkflowRequest(
            sop="normalize",
            namespace="engineering",
            required_capabilities=(NORMALIZE, NORMALIZE),
        )
    with pytest.raises(ValueError, match="credential values"):
        WorkflowFixture(
            arguments={"password": "synthetic-secret-value"},
            expected_output={"ok": True},
        )
    with pytest.raises(ValueError, match="matching expected and observed"):
        WorkflowValidationEvidence(
            trace=TRACE,
            manifest_sha256="0" * 64,
            status="passed",
            run_id="run-1",
            expected_output={"ok": True},
            observed_output={"ok": False},
        )


def run(
    tmp_path: Path, *documents: dict[str, Any], expected: object | None = None
) -> tuple[WorkflowAcceptanceOutcome, ScriptedModel, BridgeExecutor]:
    model = ScriptedModel(draft_request(), *documents)
    agent, bridge = resident(tmp_path, model)
    outcome = asyncio.run(PersonalWorkflowAuthor(agent).run(user_request(), acceptance(expected)))
    agent.state.close()
    return outcome, model, bridge


def test_e2e_02_sop_becomes_a_validated_deterministic_workflow(tmp_path: Path) -> None:
    outcome, model, bridge = run(tmp_path, manifest())
    assert outcome.validation is not None and outcome.validation.status == "passed"
    assert outcome.validation.observed_output == FIXTURE["expected_output"]
    assert outcome.validation.dispatched == (NORMALIZE, COUNT)
    assert [event.asset for event in bridge.events] == [DRAFT_SPEC.identity, NORMALIZE, COUNT]

    published = publish_validated_workflow(
        outcome,
        BusinessApproval(status="approved", reviewer="workflow-owner", evidence="e2e-02 passed"),
    )
    assert published.metadata.lifecycle == "published"
    assert published.metadata.business_approval.status == "approved"
    assert published.metadata.technical_policy.status == "pending"

    calls_after_authoring = len(model.calls)
    workflows = InstalledWorkflows()
    workflows.register(published)
    replay = Gateway(
        RequestRouter(CommandRouter(SkillRegistry()), model=model),
        bridge,
        WorkflowEngine(workflows, bridge),
    )
    context = RequestContext(
        trace=TRACE, actor="engineer", namespace="engineering", message="replay", channel="local"
    )
    first = asyncio.run(
        replay.execute_workflow(context, published.metadata.identity, FIXTURE["arguments"])
    )
    second = asyncio.run(
        replay.execute_workflow(context, published.metadata.identity, FIXTURE["arguments"])
    )
    assert first.step_results[-1].data == second.step_results[-1].data == FIXTURE["expected_output"]
    assert len(model.calls) == calls_after_authoring, "deterministic replay never reaches a model"


def test_e2e_02_rejects_a_semantically_incomplete_but_valid_manifest(tmp_path: Path) -> None:
    outcome, _model, _bridge = run(
        tmp_path, manifest(omit_count=True), manifest(omit_count=True), manifest(omit_count=True)
    )
    assert outcome.validation is None
    assert outcome.draft is not None and outcome.draft.refusal == "draft_unusable"
    assert "silently omits" in " ".join(outcome.draft.attempts[-1].problems)


def test_e2e_02_wrong_observable_output_does_not_complete(tmp_path: Path) -> None:
    outcome, _model, _bridge = run(tmp_path, manifest(), expected={"counts": {"alpha": 99}})
    assert outcome.validation is not None
    assert outcome.validation.status == "failed"
    assert outcome.validation.code == "output_mismatch"
    try:
        publish_validated_workflow(
            outcome,
            BusinessApproval(status="approved", reviewer="owner", evidence="looks plausible"),
        )
    except ValueError as error:
        assert "passing validation" in str(error)
    else:
        raise AssertionError("a failed validator must block publication")


def test_e2e_02_publication_alone_does_not_authorize_execution(tmp_path: Path) -> None:
    outcome, _model, bridge = run(tmp_path, manifest())
    published = publish_validated_workflow(
        outcome,
        BusinessApproval(status="approved", reviewer="owner", evidence="fixture passed"),
    )
    workflows = InstalledWorkflows()
    workflows.register(published)
    unauthorized = BridgeExecutor(bridge.installed, LocalPolicy())
    gateway = Gateway(
        RequestRouter(CommandRouter(SkillRegistry())),
        unauthorized,
        WorkflowEngine(workflows, unauthorized),
    )
    context = RequestContext(
        trace=TRACE, actor="engineer", namespace="engineering", message="run", channel="local"
    )
    result = asyncio.run(
        gateway.execute_workflow(context, published.metadata.identity, FIXTURE["arguments"])
    )
    assert result.run.status == "failed"
    assert result.run.failure is not None and result.run.failure.code == "permission_denied"
