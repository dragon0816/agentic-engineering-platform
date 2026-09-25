"""Product gate E2E-01: bounded DUT development and guarded physical validation."""

import asyncio
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent.gateway import Gateway
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.contracts import CapabilitySpec
from capabilities.dut_engineering.handlers import (
    DUT_DEVELOP_SPEC,
    DUT_PHYSICAL_VALIDATE_SPEC,
    DutDevelopmentHandler,
    PhysicalDutValidationHandler,
)
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityHandler,
    InstalledCapabilities,
    LocalPolicy,
)
from common.assets import AssetIdentity, ExecutionDependencies
from common.base import Contract
from common.enrollment import BridgeBinding, BridgeDevice
from common.execution import TraceIdentifiers
from common.local_agent import BridgeMembership, LocalAgentRequest
from dut.adapters import DutAdapter
from dut.contracts import (
    DutCommand,
    DutDevelopmentRequest,
    DutDevelopmentResult,
    DutObservation,
    DutPhysicalValidationRequest,
    DutTarget,
    DutValidationEvidence,
    DutValidationRequest,
    ExpectedState,
    Measurement,
    MeasurementLimit,
    skill_ref,
)
from dut.runtime import (
    DutDevelopmentService,
    DutValidationService,
    PhysicalDutValidationService,
    review_dut_change,
)
from harness.contracts import (
    CandidateChange,
    CodingHarnessRequest,
    HarnessBudget,
    HarnessPlan,
    PlannedChange,
    ValidationCase,
    ValidationFailure,
    WorkspaceSnapshot,
)
from harness.runtime import CodingHarness, DeclaredCommands
from harness.workspace import BoundedWorkspace
from host_runtime.agent import LocalAgent
from host_runtime.state import SqliteLocalState
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine
from workflow.host_bridge import BridgeRegistration, LocalResource

ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = ROOT / "fixtures" / "e2e_01"
FIXTURE = json.loads((FIXTURE_ROOT / "case.json").read_text(encoding="utf-8"))
TRACE = TraceIdentifiers(trace_id="e2e01-trace", request_id="e2e01-request", span_id="e2e01-span")
SKILL = AssetIdentity(namespace="rf", name="acme-dut-control", version="1.0.0")
COMMAND = "dut_controller.validate"


class ScriptedAuthor:
    def plan(self, request: CodingHarnessRequest) -> HarnessPlan:
        return HarnessPlan(
            summary="Update the bounded controller and validate new plus regression cases.",
            changes=(PlannedChange(path=request.artifact_path, purpose="Change DUT behavior"),),
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
        return CandidateChange(
            path=request.artifact_path,
            content=json.dumps(FIXTURE["repaired_candidate"], indent=2),
        )


def validate_controller(
    workspace: BoundedWorkspace, request: CodingHarnessRequest
) -> tuple[ValidationFailure, ...]:
    raw = workspace.read(request.artifact_path)
    assert raw is not None
    controller = json.loads(raw)
    failures: list[ValidationFailure] = []
    for case in request.cases:
        supplied = case.input
        assert isinstance(supplied, dict)
        if supplied["command"] == "set_tx_power":
            observed = {"measured_dbm": supplied["requested_dbm"] * controller["tx_gain"]}
        else:
            observed = {"ready": controller["ready"]}
        if observed != case.expected:
            failures.append(
                ValidationFailure(
                    case=case.name,
                    code="output_mismatch",
                    message="Controller output did not match the committed expectation",
                    expected=case.expected,
                    observed=observed,
                )
            )
    return tuple(failures)


class WorkspaceSimulator(DutAdapter):
    mode = "simulator"

    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = 0

    def execute(self, request: DutValidationRequest, command: DutCommand) -> DutObservation:
        self.calls += 1
        controller = json.loads((self.root / "controller.json").read_text(encoding="utf-8"))
        if command.name == "set_tx_power":
            supplied = command.arguments["requested_dbm"]
            assert isinstance(supplied, (int, float)) and not isinstance(supplied, bool)
            requested = float(supplied)
            return DutObservation(
                command=command.name,
                state={"ready": controller["ready"]},
                measurements=(
                    Measurement(
                        name="tx_power",
                        value=requested * float(controller["tx_gain"]),
                        unit="dBm",
                    ),
                ),
            )
        return DutObservation(command=command.name, state={"ready": controller["ready"]})


class TrapPhysicalAdapter(DutAdapter):
    mode = "physical"

    def __init__(self) -> None:
        self.calls = 0

    def execute(self, request: DutValidationRequest, command: DutCommand) -> DutObservation:
        self.calls += 1
        raise AssertionError("a refused request reached the physical driver")


class ScriptedRouteModel:
    def __init__(self, target: AssetIdentity, arguments: dict[str, object]) -> None:
        self.target = target
        self.arguments = arguments
        self.calls: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            structured_output={
                "kind": "capability",
                "target": self.target.model_dump(mode="json"),
                "arguments": self.arguments,
            },
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "workspace"
    shutil.copytree(FIXTURE_ROOT / "workspace", root)
    return root


def coding_request(root: Path) -> CodingHarnessRequest:
    revision = BoundedWorkspace(str(root), (FIXTURE["artifact_path"],)).revision()
    return CodingHarnessRequest(
        workspace=WorkspaceSnapshot(root=str(root.resolve()), starting_revision=revision),
        requirement=FIXTURE["requirement"],
        artifact_path=FIXTURE["artifact_path"],
        allowed_paths=(FIXTURE["artifact_path"],),
        allowed_commands=(COMMAND,),
        cases=tuple(ValidationCase.model_validate(case) for case in FIXTURE["cases"]),
        skill_versions=(skill_ref(SKILL),),
        budget=HarnessBudget(max_repair_attempts=1, max_commands=4),
    )


def validation_request(revision: str, *, bridge_id: str = "bridge-company") -> DutValidationRequest:
    return DutValidationRequest(
        bridge_id=bridge_id,
        workspace_revision=revision,
        skill=SKILL,
        target=DutTarget(
            resource_id="dut-acme-001",
            device_id="acme-001",
            vendor="acme",
            model="radio-x1",
            firmware="FW-2.3",
        ),
        commands=(DutCommand(name="set_tx_power", arguments={"requested_dbm": 10.0}),),
        limits=(MeasurementLimit(name="tx_power", unit="dBm", minimum=14.5, maximum=15.5),),
        expected_state=(ExpectedState(field="ready", expected=True),),
    )


def vendor_skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": SKILL.model_dump(mode="json"),
                "owner": {"type": "team", "id": "rf"},
                "visibility": "team",
                "lifecycle": "published",
            },
            "alias": "acme_dut",
            "instructions": (
                "Use the ACME driver procedure, verify firmware, set power, then read measured "
                "power and ready state. These vendor steps are Skill content, not core logic."
            ),
            "commands": [
                {
                    "name": "develop",
                    "kind": "capability",
                    "target": DUT_DEVELOP_SPEC.identity.model_dump(mode="json"),
                },
                {
                    "name": "validate_physical",
                    "kind": "capability",
                    "target": DUT_PHYSICAL_VALIDATE_SPEC.identity.model_dump(mode="json"),
                },
            ],
        }
    )


def membership(kind: str = "company_workstation") -> BridgeMembership:
    if kind == "company_workstation":
        device = BridgeDevice(
            bridge_id="bridge-company",
            registered_by="engineer",
            device_kind=kind,
            windows_account_mode="dedicated_user",
            resource_scope="corporate_internal",
            local_isolation="single_user",
        )
        actor = "engineer"
    else:
        device = BridgeDevice(
            bridge_id="bridge-rig",
            registered_by="rig-member",
            device_kind=kind,
            windows_account_mode="shared_user",
            resource_scope="external_only",
            local_isolation="cooperative_workspace",
        )
        actor = "rig-member"
    return BridgeMembership(
        device=device,
        bindings=(BridgeBinding(bridge_id=device.bridge_id, actor=actor, role="operator"),),
    )


def harness() -> CodingHarness:
    commands = DeclaredCommands()
    commands.register(COMMAND, validate_controller)
    return CodingHarness(commands, ScriptedAuthor())


def agent_for(
    tmp_path: Path,
    spec: CapabilitySpec,
    handler: CapabilityHandler,
    input_model: type[Contract],
    output_model: type[Contract],
    route_arguments: dict[str, object],
    *,
    grant: bool = True,
    member: BridgeMembership | None = None,
) -> LocalAgent:
    chosen = member or membership()
    installed = InstalledCapabilities()
    installed.register(
        spec,
        handler,
        input_model,
        output_model,
        ExecutionDependencies(central_required=False),
    )
    grants: tuple[CapabilityGrant, ...] = ()
    if grant:
        grants = (
            CapabilityGrant(
                actor=chosen.member() or "missing",
                asset=spec.identity,
                permissions=spec.policy.required_permissions,
                policy_refs=spec.policy.policy_refs,
                approval_ref="approved-e2e-01",
            ),
        )
    bridge = BridgeExecutor(installed, LocalPolicy(grants))
    skills = SkillRegistry()
    skills.register(vendor_skill())
    model = ScriptedRouteModel(spec.identity, route_arguments)
    gateway = Gateway(
        RequestRouter(CommandRouter(skills), model=model, model_alias="company", local_only=False),
        bridge,
        WorkflowEngine(InstalledWorkflows(), bridge),
    )
    return LocalAgent(
        chosen,
        gateway,
        SqliteLocalState(tmp_path / "state.sqlite", bridge_id=chosen.device.bridge_id),
    )


def test_e2e_01_develops_repairs_and_simulates_without_physical_access(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    coding = coding_request(root)
    simulated = validation_request(coding.workspace.starting_revision)
    requested = DutDevelopmentRequest(coding=coding, simulation=simulated)
    simulator = WorkspaceSimulator(root)
    service = DutDevelopmentService(harness(), DutValidationService(simulator))
    agent = agent_for(
        tmp_path,
        DUT_DEVELOP_SPEC,
        DutDevelopmentHandler(service),
        DutDevelopmentRequest,
        DutDevelopmentResult,
        requested.model_dump(mode="json"),
    )

    outcome = asyncio.run(
        agent.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id="bridge-company",
                namespace="rf",
                message=FIXTURE["requirement"],
                trace=TRACE,
            )
        )
    )
    agent.state.close()

    assert outcome.capability is not None and outcome.capability.status == "succeeded"
    result = DutDevelopmentResult.model_validate(outcome.capability.data)
    assert result.status == "simulated_validated"
    assert result.harness.status == "validated"
    assert [item.status for item in result.harness.commands] == ["failed", "passed"]
    assert result.simulation is not None
    assert result.simulation.status == "passed"
    assert result.simulation.evidence_level == "simulated"
    assert result.simulation.skill == SKILL
    assert result.physical_gate_satisfied is False
    assert simulator.calls == 1


def test_e2e_01_refuses_unauthorized_wrong_or_unavailable_physical_requests(
    tmp_path: Path,
) -> None:
    member = membership()
    registration = BridgeRegistration(
        bridge_id=member.device.bridge_id,
        owner_id=member.device.registered_by,
        trace=TRACE,
        capabilities=(DUT_PHYSICAL_VALIDATE_SPEC,),
        local_resources=(LocalResource(resource_id="dut-acme-001", kind="dut", available=False),),
    )
    trap = TrapPhysicalAdapter()
    service = PhysicalDutValidationService(
        member,
        registration,
        installed_skill=SKILL,
        adapter=trap,
        physical_enabled=True,
    )
    requested = DutPhysicalValidationRequest(validation=validation_request("a" * 64))

    unauthorized = agent_for(
        tmp_path,
        DUT_PHYSICAL_VALIDATE_SPEC,
        PhysicalDutValidationHandler(service),
        DutPhysicalValidationRequest,
        DutValidationEvidence,
        requested.model_dump(mode="json"),
        grant=False,
        member=member,
    )
    denied = asyncio.run(
        unauthorized.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id="bridge-company",
                namespace="rf",
                message="validate the DUT",
                trace=TRACE,
            )
        )
    )
    unauthorized.state.close()
    assert denied.capability is not None
    assert denied.capability.failure is not None
    assert denied.capability.failure.code == "permission_denied"
    assert denied.capability.handler_invoked is False

    unavailable = agent_for(
        tmp_path,
        DUT_PHYSICAL_VALIDATE_SPEC,
        PhysicalDutValidationHandler(service),
        DutPhysicalValidationRequest,
        DutValidationEvidence,
        requested.model_dump(mode="json"),
        member=member,
    )
    refused = asyncio.run(
        unavailable.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id="bridge-company",
                namespace="rf",
                message="validate the DUT",
                trace=TRACE,
            )
        )
    )
    unavailable.state.close()
    assert refused.capability is not None and refused.capability.failure is not None
    assert refused.capability.failure.code == "dut_unavailable"

    wrong = agent_for(
        tmp_path,
        DUT_PHYSICAL_VALIDATE_SPEC,
        PhysicalDutValidationHandler(service),
        DutPhysicalValidationRequest,
        DutValidationEvidence,
        requested.model_dump(mode="json"),
        member=member,
    )
    wrong_device = asyncio.run(
        wrong.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id="another-bridge",
                namespace="rf",
                message="validate the DUT",
                trace=TRACE,
            )
        )
    )
    wrong.state.close()
    assert wrong_device.refusal == "device_identity_mismatch"
    assert trap.calls == 0


def test_e2e_01_simulation_and_failed_measurement_cannot_pass_human_review(
    tmp_path: Path,
) -> None:
    root = workspace(tmp_path)
    simulator = WorkspaceSimulator(root)
    asked = validation_request("a" * 64)
    evidence = DutValidationService(simulator).run(TRACE, asked)
    assert evidence.status == "failed"
    assert evidence.outcomes[0].passed is False
    assert evidence.evidence_level == "simulated"
    with pytest.raises(ValueError, match="production-like physical evidence"):
        review_dut_change(
            implementation_digest="b" * 64,
            evidence=evidence,
            reviewer="rf-owner",
            approval_ref="review-1",
            approved=True,
        )


def test_e2e_01_contracts_reject_secret_material_and_skill_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="credential"):
        DutCommand(name="connect", arguments={"password": "do-not-store"})

    root = workspace(tmp_path)
    coding = coding_request(root)
    other = AssetIdentity(namespace="rf", name="other-vendor", version="1.0.0")
    with pytest.raises(ValueError, match="exact Skill"):
        DutDevelopmentRequest(
            coding=coding,
            simulation=validation_request(coding.workspace.starting_revision).model_copy(
                update={"skill": other}
            ),
        )
