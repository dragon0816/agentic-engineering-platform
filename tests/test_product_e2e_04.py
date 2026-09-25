"""Product gate E2E-04: Software report to governed release metadata."""

import asyncio
import json
import shutil
from collections.abc import Iterator, Mapping
from pathlib import Path

import pytest
from pydantic import ValidationError

from agent.gateway import Gateway
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.runtime import (
    CapabilityGrant,
    CapabilityInvocation,
    InstalledCapabilities,
    LocalPolicy,
)
from capabilities.software_evolution.handlers import (
    SOFTWARE_CAPTURE_SPEC,
    SOFTWARE_DEVELOP_SPEC,
    SoftwareCaptureHandler,
    SoftwareDevelopHandler,
)
from common.assets import (
    AssetIdentity,
    AssetMetadata,
    BusinessApproval,
    Compatibility,
    ExecutionDependencies,
    Owner,
)
from common.enrollment import BridgeBinding, BridgeDevice
from common.execution import CapabilityResult, RequestContext, TraceIdentifiers
from common.local_agent import BridgeMembership, LocalAgentRequest
from harness.contracts import CandidateChange, HarnessPlan, PlannedChange, ValidationCase
from harness.runtime import CodingHarness, DeclaredCommands
from harness.transform import validate_json_transform
from harness.workspace import BoundedWorkspace
from host_runtime.agent import LocalAgent
from host_runtime.state import SqliteLocalState
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent
from software.evolution import (
    ExternalRepository,
    PullRequestReview,
    SoftwareCatalog,
    SoftwareDevelopmentRequest,
    SoftwareDevelopmentResult,
    SoftwareFailureReport,
    SoftwareImprovementRequest,
    SoftwareInterface,
    SoftwareManifest,
    SoftwareRelease,
    approve_improvement,
    approve_pull_request,
    publish_software,
    record_merge,
    record_release,
)
from software.runtime import InstalledRepositories, InstalledRepository, SoftwareDevelopmentService
from software.source_control import InertSourceControlAdapter
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

ROOT = Path(__file__).resolve().parent
FIXTURE_ROOT = ROOT / "fixtures" / "e2e_04"
FIXTURE = json.loads((FIXTURE_ROOT / "case.json").read_text(encoding="utf-8"))
V1 = AssetIdentity(namespace="engineering", name="record-transformer", version="1.0.0")
V2 = AssetIdentity(namespace="engineering", name="record-transformer", version="1.1.0")
TRACE = TraceIdentifiers(trace_id="e2e04-trace", request_id="e2e04-request", span_id="e2e04-span")
COMMAND = "record-transformer.validate"
LOCATOR = "fixture://engineering/record-transformer"


class SoftwareAuthor:
    def __init__(self, candidate: Mapping[str, object] | None = None) -> None:
        self.candidate = dict(candidate or FIXTURE["fixed_candidate"])

    def plan(self, request: object) -> HarnessPlan:
        return HarnessPlan(
            summary="Fix the reported conversion and run the repository regression suite.",
            changes=(PlannedChange(path="transform.json", purpose="Correct age conversion"),),
            validation_commands=(COMMAND,),
        )

    def initial_change(self, request: object, plan: HarnessPlan) -> CandidateChange:
        return CandidateChange(path="transform.json", content=json.dumps(self.candidate, indent=2))

    def repair(
        self, request: object, plan: HarnessPlan, failure: object, attempt: int
    ) -> CandidateChange:
        return self.initial_change(request, plan)


class SoftwareRouteModel:
    def __init__(self, routed: SoftwareFailureReport | SoftwareDevelopmentRequest) -> None:
        self.routed = routed
        self.calls: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        target = (
            SOFTWARE_CAPTURE_SPEC.identity
            if isinstance(self.routed, SoftwareFailureReport)
            else SOFTWARE_DEVELOP_SPEC.identity
        )
        return ModelResponse(
            trace=request.trace,
            model_alias=request.model_alias,
            structured_output={
                "kind": "capability",
                "target": target.model_dump(mode="json"),
                "arguments": self.routed.model_dump(mode="json"),
            },
        )

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def copy_repository(tmp_path: Path, *, fixed: bool = False) -> Path:
    root = tmp_path / "repository"
    shutil.copytree(FIXTURE_ROOT / "repository", root)
    if fixed:
        (root / "transform.json").write_text(
            json.dumps(FIXTURE["fixed_candidate"], indent=2), encoding="utf-8"
        )
    return root


def manifest(root: Path) -> SoftwareManifest:
    revision = BoundedWorkspace(str(root), ("transform.json",)).revision()
    return SoftwareManifest(
        metadata=AssetMetadata(
            identity=V1,
            owner=Owner(type="team", id="engineering-software"),
            visibility="team",
            lifecycle="published",
            compatibility=Compatibility(runtime="aep>=0.1", platforms=("windows",)),
            business_approval=BusinessApproval(
                status="approved", reviewer="software-owner", evidence="v1 release approved"
            ),
            validation_refs=("software-validation:v1",),
            evaluation_refs=("software-case:existing-category-normalization",),
        ),
        repository=ExternalRepository(provider="fixture", locator=LOCATOR, revision=revision),
        interfaces=(
            SoftwareInterface(
                name="transform-records",
                input_contract="records.input.v1",
                output_contract="records.output.v1",
            ),
        ),
        release=SoftwareRelease(
            release_ref="fixture-release:1.0.0",
            source_revision=revision,
            evidence_refs=("software-validation:v1",),
        ),
    )


def report(
    *, expected: object | None = None, observed: object | None = None
) -> SoftwareFailureReport:
    return SoftwareFailureReport(
        target=V1,
        trace=TRACE,
        expected_behavior=FIXTURE["expected_behavior"],
        actual_behavior=FIXTURE["actual_behavior"],
        evidence=tuple(FIXTURE["evidence"]),
        example_input=FIXTURE["example_input"],
        expected_output=FIXTURE["expected_output"] if expected is None else expected,
        observed_output=FIXTURE["observed_output"] if observed is None else observed,
        reproduction_environment=FIXTURE["reproduction_environment"],
        acceptance_criteria=tuple(FIXTURE["acceptance_criteria"]),
    )


def skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "software-maintenance",
                    "version": "1.0.0",
                },
                "owner": {"type": "team", "id": "engineering-software"},
                "visibility": "team",
                "lifecycle": "published",
            },
            "alias": "software",
            "instructions": "Capture and develop bounded Software improvements.",
            "commands": [
                {
                    "name": "report",
                    "kind": "capability",
                    "target": SOFTWARE_CAPTURE_SPEC.identity.model_dump(mode="json"),
                },
                {
                    "name": "develop",
                    "kind": "capability",
                    "target": SOFTWARE_DEVELOP_SPEC.identity.model_dump(mode="json"),
                },
            ],
        }
    )


def resident(
    tmp_path: Path,
    catalog: SoftwareCatalog,
    root: Path,
    model: SoftwareRouteModel,
    *,
    author: SoftwareAuthor | None = None,
) -> tuple[LocalAgent, BridgeExecutor, InertSourceControlAdapter]:
    commands = DeclaredCommands()
    commands.register(COMMAND, validate_json_transform)
    harness = CodingHarness(commands, author or SoftwareAuthor())
    repositories = InstalledRepositories()
    repositories.register(
        InstalledRepository(
            locator=LOCATOR,
            workspace_root=str(root.resolve()),
            artifact_path="transform.json",
            allowed_paths=("transform.json",),
            validation_command=COMMAND,
            regression_cases=tuple(
                ValidationCase.model_validate(item) for item in FIXTURE["regression_cases"]
            ),
            skill_versions=("engineering.software-maintenance@1.0.0",),
        )
    )
    source_control = InertSourceControlAdapter()
    service = SoftwareDevelopmentService(catalog, repositories, harness, source_control)
    installed = InstalledCapabilities()
    installed.register(
        SOFTWARE_CAPTURE_SPEC,
        SoftwareCaptureHandler(catalog),
        SoftwareFailureReport,
        SoftwareImprovementRequest,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        SOFTWARE_DEVELOP_SPEC,
        SoftwareDevelopHandler(service),
        SoftwareDevelopmentRequest,
        SoftwareDevelopmentResult,
        ExecutionDependencies(central_required=False),
    )
    grants = tuple(
        CapabilityGrant(
            actor="engineer",
            asset=spec.identity,
            permissions=spec.policy.required_permissions,
            policy_refs=spec.policy.policy_refs,
            approval_ref="approved-software-workspace-write"
            if spec.policy.approval_required
            else None,
        )
        for spec in (SOFTWARE_CAPTURE_SPEC, SOFTWARE_DEVELOP_SPEC)
    )
    bridge = BridgeExecutor(installed, LocalPolicy(grants))
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
    return LocalAgent(membership, gateway, state), bridge, source_control


def send(
    agent: LocalAgent,
    model: SoftwareRouteModel,
    routed: SoftwareFailureReport | SoftwareDevelopmentRequest,
    message: str,
) -> CapabilityResult:
    model.routed = routed
    outcome = asyncio.run(
        agent.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id="bridge-company",
                namespace="engineering",
                message=message,
                trace=TRACE,
            )
        )
    )
    assert outcome.capability is not None
    return outcome.capability


def approved(request: SoftwareImprovementRequest) -> SoftwareImprovementRequest:
    return approve_improvement(
        request,
        BusinessApproval(
            status="approved",
            reviewer="software-owner",
            evidence="The supplied fixture reproduces an owned Software defect.",
        ),
    )


def test_e2e_04_report_becomes_reviewable_change_and_versioned_release(tmp_path: Path) -> None:
    root = copy_repository(tmp_path)
    v1 = manifest(root)
    catalog = SoftwareCatalog()
    catalog.register(v1)
    model = SoftwareRouteModel(report())
    agent, bridge, source_control = resident(tmp_path, catalog, root, model)

    captured_result = send(agent, model, report(), "The published transformer leaves age as text.")
    assert captured_result.status == "succeeded"
    improvement = SoftwareImprovementRequest.model_validate(captured_result.data)
    assert improvement.target == V1
    assert improvement.owner == v1.metadata.owner
    assert improvement.repository == v1.repository
    assert improvement.development_approval.status == "pending"
    assert bridge.events[-1].asset == SOFTWARE_CAPTURE_SPEC.identity

    before = (root / "transform.json").read_bytes()
    refused = send(
        agent,
        model,
        SoftwareDevelopmentRequest(improvement=improvement),
        "Develop the reported Software fix.",
    )
    assert refused.status == "failed"
    assert refused.failure is not None and refused.failure.code == "development_not_approved"
    assert (root / "transform.json").read_bytes() == before

    improvement = approved(improvement)
    developed_result = send(
        agent,
        model,
        SoftwareDevelopmentRequest(improvement=improvement),
        "Develop the approved Software fix.",
    )
    assert developed_result.status == "succeeded"
    developed = SoftwareDevelopmentResult.model_validate(developed_result.data)
    assert developed.status == "validated"
    assert developed.reproduction.status == "failed"
    assert {item.case for item in developed.reproduction.failures} == {
        "reported-failure-acceptance"
    }
    assert developed.harness is not None and developed.harness.status == "validated"
    assert developed.pull_request is not None
    assert developed.pull_request.changes == developed.harness.changes
    assert developed.pull_request.external_write is False
    assert developed.release_ready is developed.merged is developed.released is False
    assert source_control.external_writes == 0
    assert bridge.events[-1].asset == SOFTWARE_DEVELOP_SPEC.identity

    with pytest.raises(ValueError, match="approved source-control review"):
        approve_pull_request(
            developed.pull_request,
            PullRequestReview(
                status="rejected",
                reviewer="repository-maintainer",
                evidence="The rejected review cannot be merged.",
            ),
        )
    reviewed = approve_pull_request(
        developed.pull_request,
        PullRequestReview(
            status="approved",
            reviewer="repository-maintainer",
            evidence="Patch and validation evidence reviewed.",
        ),
    )
    merged_revision = BoundedWorkspace(str(root), ("transform.json",)).revision()
    merge = record_merge(
        reviewed,
        merged_revision=merged_revision,
        merged_by="repository-maintainer",
        evidence_ref="fixture-pr:1",
    )
    release = record_release(
        v1,
        merge,
        identity=V2,
        release_ref="fixture-release:1.1.0",
        released_by="release-owner",
        evidence_ref="fixture-release-evidence:1.1.0",
    )
    published = publish_software(
        v1,
        release,
        BusinessApproval(
            status="approved",
            reviewer="software-owner",
            evidence="Release 1.1.0 is approved for platform representation.",
        ),
    )
    catalog.register(published)
    assert published.metadata.identity == V2
    assert published.repository.revision == merged_revision
    assert published.release.previous_version == V1
    assert published.metadata.technical_policy == v1.metadata.technical_policy
    assert merge.reviewed_by == "repository-maintainer"
    assert catalog.get(V1) == v1 and catalog.get(V2) == published
    empty_catalog = SoftwareCatalog()
    with pytest.raises(ValueError, match="rollback version"):
        empty_catalog.register(published)

    execution = asyncio.run(
        bridge.execute(
            CapabilityInvocation(
                context=RequestContext(
                    trace=TRACE,
                    actor="engineer",
                    namespace="engineering",
                    message="run the published Software",
                    channel="local",
                ),
                target=V2,
            )
        )
    )
    assert execution.status == "unavailable"
    assert execution.failure is not None and execution.failure.code == "capability_not_installed"
    agent.state.close()


def test_e2e_04_unreproduced_issue_cannot_be_marked_fixed(tmp_path: Path) -> None:
    root = copy_repository(tmp_path, fixed=True)
    catalog = SoftwareCatalog()
    catalog.register(manifest(root))
    claimed = report(expected=FIXTURE["expected_output"], observed=FIXTURE["expected_output"])
    model = SoftwareRouteModel(claimed)
    agent, _bridge, source_control = resident(tmp_path, catalog, root, model)
    capture = send(agent, model, claimed, "This already-correct example is reported as broken.")
    improvement = approved(SoftwareImprovementRequest.model_validate(capture.data))
    result = send(
        agent,
        model,
        SoftwareDevelopmentRequest(improvement=improvement),
        "Develop the approved Software fix.",
    )
    developed = SoftwareDevelopmentResult.model_validate(result.data)
    assert developed.status == "unreproduced"
    assert developed.harness is None and developed.pull_request is None
    assert developed.failure is not None and developed.failure.code == "issue_not_reproduced"
    assert source_control.prepared == ()
    agent.state.close()


def test_e2e_04_repository_regression_blocks_pr_candidate(tmp_path: Path) -> None:
    root = copy_repository(tmp_path)
    catalog = SoftwareCatalog()
    catalog.register(manifest(root))
    model = SoftwareRouteModel(report())
    agent, _bridge, source_control = resident(
        tmp_path,
        catalog,
        root,
        model,
        author=SoftwareAuthor(FIXTURE["regression_breaking_candidate"]),
    )
    capture = send(agent, model, report(), "The published transformer leaves age as text.")
    improvement = approved(SoftwareImprovementRequest.model_validate(capture.data))
    result = send(
        agent,
        model,
        SoftwareDevelopmentRequest(improvement=improvement),
        "Develop the approved Software fix.",
    )
    developed = SoftwareDevelopmentResult.model_validate(result.data)
    assert developed.status == "failed"
    assert developed.harness is not None and developed.harness.status == "failed"
    assert {item.case for item in developed.harness.commands[-1].failures} == {
        "existing-category-normalization"
    }
    assert developed.pull_request is None and source_control.prepared == ()
    agent.state.close()


def test_e2e_04_contracts_reject_source_content_and_credentials(tmp_path: Path) -> None:
    root = copy_repository(tmp_path)
    payload = manifest(root).model_dump(mode="json")
    payload["source_code"] = "must remain in source control"
    with pytest.raises(ValidationError):
        SoftwareManifest.model_validate(payload)
    unsafe = report().model_dump(mode="json")
    unsafe["evidence"] = ["access_token=never-store-this"]
    with pytest.raises(ValidationError, match="credential"):
        SoftwareFailureReport.model_validate(unsafe)
