"""Product gate E2E-03: bounded coding/transformation with external validation."""

import asyncio
import json
import shutil
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest

from agent.gateway import Gateway
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.coding_harness.handlers import CODING_HARNESS_SPEC, CodingHarnessHandler
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import ExecutionDependencies
from common.enrollment import BridgeBinding, BridgeDevice
from common.execution import TraceIdentifiers
from common.local_agent import BridgeMembership, LocalAgentRequest
from harness.contracts import (
    CandidateChange,
    CodingHarnessRequest,
    CodingHarnessResult,
    HarnessBudget,
    HarnessPlan,
    PlannedChange,
    ValidationCase,
    WorkspaceSnapshot,
)
from harness.runtime import CodingHarness, DeclaredCommands
from harness.transform import validate_json_transform
from harness.workspace import BoundedWorkspace
from host_runtime.agent import LocalAgent
from host_runtime.state import SqliteLocalState
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = ROOT / "fixtures" / "e2e_03"
FIXTURE = json.loads((FIXTURE_ROOT / "case.json").read_text(encoding="utf-8"))
TRACE = TraceIdentifiers(trace_id="e2e03-trace", request_id="e2e03-request", span_id="e2e03-span")
COMMAND = "json_transform.validate"


class ScriptedAuthor:
    """A provider-neutral author fixture; the Harness still decides completion."""

    def __init__(self, *, repaired: Mapping[str, object] | None = None) -> None:
        self.repaired = dict(repaired) if repaired is not None else FIXTURE["repaired_candidate"]
        self.failures: list[object] = []

    def plan(self, request: CodingHarnessRequest) -> HarnessPlan:
        return HarnessPlan(
            summary="Implement the bounded record transformation and verify all committed cases.",
            changes=(
                PlannedChange(
                    path=request.artifact_path,
                    purpose="Define the deterministic field mapping and conversions",
                ),
            ),
            validation_commands=(COMMAND,),
        )

    def initial_change(self, request: CodingHarnessRequest, plan: HarnessPlan) -> CandidateChange:
        return CandidateChange(
            path=request.artifact_path,
            content=json.dumps(FIXTURE["initial_candidate"], indent=2),
        )

    def repair(
        self,
        request: CodingHarnessRequest,
        plan: HarnessPlan,
        failure: object,
        attempt: int,
    ) -> CandidateChange:
        self.failures.append(failure)
        return CandidateChange(
            path=request.artifact_path,
            content=json.dumps(self.repaired, indent=2),
        )


class ScriptedRouteModel:
    def __init__(self, request: CodingHarnessRequest) -> None:
        self.request = request
        self.calls: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            structured_output={
                "kind": "capability",
                "target": CODING_HARNESS_SPEC.identity.model_dump(mode="json"),
                "arguments": self.request.model_dump(mode="json"),
            },
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    shutil.copytree(FIXTURE_ROOT / "workspace", root)
    return root


def request_for(
    root: Path, *, repairs: int = 1, commands: tuple[str, ...] = (COMMAND,)
) -> CodingHarnessRequest:
    revision = BoundedWorkspace(str(root), (FIXTURE["artifact_path"],)).revision()
    return CodingHarnessRequest(
        workspace=WorkspaceSnapshot(root=str(root.resolve()), starting_revision=revision),
        requirement=FIXTURE["requirement"],
        artifact_path=FIXTURE["artifact_path"],
        allowed_paths=(FIXTURE["artifact_path"],),
        allowed_commands=commands,
        cases=tuple(ValidationCase.model_validate(case) for case in FIXTURE["cases"]),
        skill_versions=("engineering.record-transformation@1.0.0",),
        budget=HarnessBudget(max_repair_attempts=repairs, max_commands=4),
    )


def harness(author: ScriptedAuthor) -> CodingHarness:
    commands = DeclaredCommands()
    commands.register(COMMAND, validate_json_transform)
    return CodingHarness(commands, author)


def skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "record-transformation",
                    "version": "1.0.0",
                },
                "owner": {"type": "team", "id": "engineering"},
                "visibility": "team",
                "lifecycle": "published",
            },
            "alias": "transform",
            "instructions": "Plan and validate a bounded record transformation.",
            "commands": [
                {
                    "name": "implement",
                    "kind": "capability",
                    "target": CODING_HARNESS_SPEC.identity.model_dump(mode="json"),
                }
            ],
        }
    )


def resident(
    tmp_path: Path, run_request: CodingHarnessRequest, author: ScriptedAuthor
) -> tuple[LocalAgent, BridgeExecutor, ScriptedRouteModel]:
    installed = InstalledCapabilities()
    installed.register(
        CODING_HARNESS_SPEC,
        CodingHarnessHandler(harness(author)),
        CodingHarnessRequest,
        CodingHarnessResult,
        ExecutionDependencies(central_required=False),
    )
    grant = CapabilityGrant(
        actor="engineer",
        asset=CODING_HARNESS_SPEC.identity,
        permissions=CODING_HARNESS_SPEC.policy.required_permissions,
        policy_refs=CODING_HARNESS_SPEC.policy.policy_refs,
        approval_ref="approved-e2e-03-workspace-write",
    )
    bridge = BridgeExecutor(installed, LocalPolicy((grant,)))
    skills = SkillRegistry()
    skills.register(skill())
    model = ScriptedRouteModel(run_request)
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
    return LocalAgent(membership, gateway, state), bridge, model


def test_e2e_03_repairs_a_failed_transform_and_preserves_regressions(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    asked = request_for(root)
    author = ScriptedAuthor()
    agent, bridge, model = resident(tmp_path, asked, author)
    outcome = asyncio.run(
        agent.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id="bridge-company",
                namespace="engineering",
                message=FIXTURE["requirement"],
                trace=TRACE,
            )
        )
    )
    agent.state.close()

    assert outcome.capability is not None and outcome.capability.status == "succeeded"
    result = CodingHarnessResult.model_validate(outcome.capability.data)
    assert result.status == "validated"
    assert [item.status for item in result.commands] == ["failed", "passed"]
    assert {failure.case for failure in result.commands[0].failures} == {"new-age-conversion"}
    assert len(author.failures) == 1
    assert result.plan.changes[0].path == "transform.json"
    assert len(result.changes) == 2
    assert result.workspace == asked.workspace
    assert '"operations": []' in result.changes[0].patch
    assert '+        "integer"' in result.changes[1].patch
    assert result.artifact is not None
    assert result.committed is result.published is False
    assert result.skill_versions == ("engineering.record-transformation@1.0.0",)
    assert [event.kind for event in result.events] == [
        "planned",
        "changed",
        "validation_failed",
        "repair_requested",
        "changed",
        "validated",
    ]
    assert model.calls and bridge.events[-1].asset == CODING_HARNESS_SPEC.identity


def test_e2e_03_failed_validation_and_budget_prevent_completion(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    result = harness(ScriptedAuthor()).run(TRACE, request_for(root, repairs=0))
    assert result.status == "failed"
    assert result.failure is not None and result.failure.code == "repair_budget_exceeded"
    assert result.commands[-1].status == "failed"
    assert result.artifact is None


def test_e2e_03_regression_failure_blocks_a_new_case_that_passes(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    regression_break = {
        "fields": [
            {"target": "category", "source": "category", "operations": ["strip", "lower"]},
            {"target": "age", "source": "age_new", "operations": []},
        ]
    }
    result = harness(ScriptedAuthor(repaired=regression_break)).run(TRACE, request_for(root))
    assert result.status == "failed"
    assert result.commands[-1].status == "failed"
    assert {failure.case for failure in result.commands[-1].failures} == {"existing-normalization"}


def test_e2e_03_contract_and_runtime_refuse_unbounded_scope(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    with pytest.raises(ValueError, match="without traversal"):
        PlannedChange(path="../outside.json", purpose="escape")
    with pytest.raises(ValueError, match="credential"):
        ValidationCase(
            name="unsafe",
            kind="new",
            input={"password": "never-store-this"},
            expected={"ok": True},
        )

    asked = request_for(root)

    class BadPlan(ScriptedAuthor):
        def plan(self, request: CodingHarnessRequest) -> HarnessPlan:
            return HarnessPlan(
                summary="Attempt undeclared validation",
                changes=(PlannedChange(path=request.artifact_path, purpose="change"),),
                validation_commands=("shell.arbitrary",),
            )

    result = harness(BadPlan()).run(TRACE, asked)
    assert result.status == "needs_input"
    assert result.failure is not None and result.failure.code == "plan_command_not_allowed"
    assert result.changes == ()
