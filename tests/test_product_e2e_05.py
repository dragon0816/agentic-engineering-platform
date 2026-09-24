"""Product gate E2E-05: grounded feedback to governed Knowledge vNext."""

import asyncio
import re
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

from agent.gateway import Gateway
from agent.routing import CommandRouter, RequestRouter
from agent.skills import SkillManifest, SkillRegistry
from capabilities.knowledge_evolution.handlers import (
    KNOWLEDGE_CANDIDATE_SPEC,
    KnowledgeCandidateHandler,
)
from capabilities.knowledge_query.handlers import KNOWLEDGE_QUERY_SPEC, KnowledgeQueryHandler
from capabilities.runtime import CapabilityGrant, InstalledCapabilities, LocalPolicy
from common.assets import (
    AssetIdentity,
    AssetMetadata,
    BusinessApproval,
    ExecutionDependencies,
    Owner,
)
from common.enrollment import BridgeBinding, BridgeDevice
from common.execution import TraceIdentifiers
from common.local_agent import BridgeMembership, LocalAgentRequest
from host_runtime.agent import LocalAgent
from host_runtime.state import SqliteLocalState
from knowledge.evolution import (
    KnowledgeAnswerRecord,
    KnowledgeCandidate,
    KnowledgeCandidateRequest,
    KnowledgeCatalog,
    KnowledgeEvaluationCase,
    KnowledgeManifest,
    KnowledgeQueryRequest,
    approve_candidate,
    authorize_improvement,
    capture_improvement,
    create_candidate,
    decision_digest,
    knowledge_digest,
    publish_candidate,
    raw_digest,
    validate_candidate,
)
from knowledge.raw import RawIndex
from knowledge.vault import PlannedPage, Vault, WritePlan, provenance_lines
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent
from workflow.dispatch import BridgeExecutor
from workflow.engine import InstalledWorkflows, WorkflowEngine

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "e2e_05" / "vault"
V1 = AssetIdentity(namespace="engineering", name="widget-guide", version="1.0.0")
V2 = AssetIdentity(namespace="engineering", name="widget-guide", version="1.1.0")
QUERY_TRACE = TraceIdentifiers(
    trace_id="e2e05-query", request_id="e2e05-request", span_id="e2e05-span"
)


class ProductKnowledgeModel:
    """Routes requests and synthesizes only from numbered retrieved passages."""

    def __init__(self, routed: KnowledgeQueryRequest | KnowledgeCandidateRequest) -> None:
        self.routed = routed
        self.requests: list[ModelRequest] = []

    @staticmethod
    def _passage(prompt: str, phrase: str) -> int:
        for match in re.finditer(r"^\[(\d+)\] (.+)$", prompt, re.MULTILINE):
            if phrase.casefold() in match.group(2).casefold():
                return int(match.group(1))
        return 1

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if request.output_contract == "platform.route-proposal.v1":
            target = (
                KNOWLEDGE_QUERY_SPEC.identity
                if isinstance(self.routed, KnowledgeQueryRequest)
                else KNOWLEDGE_CANDIDATE_SPEC.identity
            )
            output: object = {
                "kind": "capability",
                "target": target.model_dump(mode="json"),
                "arguments": self.routed.model_dump(mode="json"),
            }
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                structured_output=output,
            )
        prompt = request.messages[-1].text
        if "blue" in prompt.split("Question:", 1)[1].split("\n", 1)[0].casefold():
            number = self._passage(prompt, "Widget is blue")
            text = f"Widget is blue [{number}]."
        elif "safe mode" in prompt.split("Question:", 1)[1].split("\n", 1)[0].casefold():
            number = self._passage(prompt, "Turbo mode is unsupported")
            occurrences = prompt.count("Safe mode requires firmware 2.0")
            text = (
                f"Safe mode requires firmware 2.0 [{number}]."
                if occurrences >= 2
                else f"Widget supports Legacy mode [{number}]."
            )
        else:
            number = self._passage(prompt, "Turbo mode is unsupported")
            text = f"Widget supports Legacy mode [{number}]."
        return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=text)

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


class RegressionBreakingModel(ProductKnowledgeModel):
    def generate(self, request: ModelRequest) -> ModelResponse:
        if request.output_contract == "platform.route-proposal.v1":
            return super().generate(request)
        prompt = request.messages[-1].text
        question = prompt.split("Question:", 1)[1].split("\n", 1)[0].casefold()
        if "legacy" in question:
            number = self._passage(prompt, "Turbo mode is unsupported")
            return ModelResponse(
                trace=request.trace,
                model_alias=request.model_alias,
                text=f"Safe mode requires firmware 2.0 [{number}].",
            )
        return super().generate(request)


def copy_vault(tmp_path: Path) -> Vault:
    root = tmp_path / "published-v1"
    shutil.copytree(FIXTURE, root)
    return Vault(root)


def manifest(vault: Vault) -> KnowledgeManifest:
    return KnowledgeManifest(
        metadata=AssetMetadata(
            identity=V1,
            owner=Owner(type="team", id="engineering-knowledge"),
            visibility="team",
            lifecycle="published",
            business_approval=BusinessApproval(
                status="approved", reviewer="domain-owner", evidence="baseline reviewed"
            ),
            validation_refs=("knowledge-eval:baseline",),
            evaluation_refs=("knowledge-case:legacy-regression",),
        ),
        domain="engineering",
        vault_ref=str(vault.root.resolve()),
        raw_sha256=raw_digest(vault),
        decisions_sha256=decision_digest(vault),
        content_sha256=knowledge_digest(vault),
        evaluation_case_ids=("legacy-regression",),
    )


def skill() -> SkillManifest:
    return SkillManifest.model_validate(
        {
            "metadata": {
                "identity": {
                    "namespace": "engineering",
                    "name": "knowledge-question-answering",
                    "version": "1.0.0",
                },
                "owner": {"type": "team", "id": "engineering-knowledge"},
                "visibility": "team",
                "lifecycle": "published",
            },
            "alias": "knowledge",
            "instructions": "Answer from exact published Knowledge with Raw citations.",
            "commands": [
                {
                    "name": "ask",
                    "kind": "capability",
                    "target": KNOWLEDGE_QUERY_SPEC.identity.model_dump(mode="json"),
                },
                {
                    "name": "improve",
                    "kind": "capability",
                    "target": KNOWLEDGE_CANDIDATE_SPEC.identity.model_dump(mode="json"),
                },
            ],
        }
    )


def resident(
    tmp_path: Path, catalog: KnowledgeCatalog, model: ProductKnowledgeModel
) -> tuple[LocalAgent, BridgeExecutor]:
    installed = InstalledCapabilities()
    installed.register(
        KNOWLEDGE_QUERY_SPEC,
        KnowledgeQueryHandler(catalog, model, alias="knowledge-answerer"),
        KnowledgeQueryRequest,
        KnowledgeAnswerRecord,
        ExecutionDependencies(central_required=False),
    )
    installed.register(
        KNOWLEDGE_CANDIDATE_SPEC,
        KnowledgeCandidateHandler(catalog, workspace_root=tmp_path),
        KnowledgeCandidateRequest,
        KnowledgeCandidate,
        ExecutionDependencies(central_required=False),
    )
    grants = (
        CapabilityGrant(
            actor="engineer",
            asset=KNOWLEDGE_QUERY_SPEC.identity,
            permissions=KNOWLEDGE_QUERY_SPEC.policy.required_permissions,
            policy_refs=KNOWLEDGE_QUERY_SPEC.policy.policy_refs,
        ),
        CapabilityGrant(
            actor="engineer",
            asset=KNOWLEDGE_CANDIDATE_SPEC.identity,
            permissions=KNOWLEDGE_CANDIDATE_SPEC.policy.required_permissions,
            policy_refs=KNOWLEDGE_CANDIDATE_SPEC.policy.policy_refs,
            approval_ref="approved-knowledge-candidate-workspace-write",
        ),
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
    return LocalAgent(membership, gateway, state), bridge


def ask(
    agent: LocalAgent, model: ProductKnowledgeModel, asset: AssetIdentity, question: str
) -> KnowledgeAnswerRecord:
    model.routed = KnowledgeQueryRequest(asset=asset, question=question)
    outcome = asyncio.run(
        agent.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id="bridge-company",
                namespace="engineering",
                message=question,
                trace=QUERY_TRACE,
            )
        )
    )
    assert outcome.capability is not None and outcome.capability.status == "succeeded"
    return KnowledgeAnswerRecord.model_validate(outcome.capability.data)


def build_candidate(
    agent: LocalAgent,
    model: ProductKnowledgeModel,
    request: KnowledgeCandidateRequest,
) -> KnowledgeCandidate:
    model.routed = request
    outcome = asyncio.run(
        agent.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id="bridge-company",
                namespace="engineering",
                message="Prepare the approved Knowledge candidate.",
                trace=TraceIdentifiers(
                    trace_id="e2e05-candidate",
                    request_id="e2e05-candidate-request",
                    span_id="e2e05-candidate-span",
                ),
            )
        )
    )
    assert outcome.capability is not None and outcome.capability.status == "succeeded"
    return KnowledgeCandidate.model_validate(outcome.capability.data)


def cases() -> tuple[KnowledgeEvaluationCase, ...]:
    return (
        KnowledgeEvaluationCase(
            case_id="safe-mode-feedback",
            kind="new",
            question="What firmware does Safe mode require?",
            required_facts=("Safe mode requires firmware 2.0",),
            forbidden_facts=("Turbo mode is recommended",),
        ),
        KnowledgeEvaluationCase(
            case_id="legacy-regression",
            kind="regression",
            question="Does the Widget support Legacy mode?",
            required_facts=("Widget supports Legacy mode",),
            forbidden_facts=("Turbo mode is recommended",),
        ),
    )


def candidate_plan(vault: Vault) -> WritePlan:
    source = RawIndex.scan(vault).entries[0].source
    source_id, source_sha = provenance_lines(source)
    return WritePlan(
        source=source,
        summary="Add the missing Safe mode firmware requirement.",
        pages=(
            PlannedPage(
                path="wiki/sources/Guide.md",
                action="update",
                content=(
                    f"---\ntitle: Guide\ntype: source\n{source_id}\n{source_sha}\n---\n"
                    "Widget supports Legacy mode.\n\n"
                    "Safe mode requires firmware 2.0.\n"
                ),
            ),
            PlannedPage(
                path="wiki/entities/Widget.md",
                action="update",
                content=(
                    "---\ntitle: Widget\ntype: entity\n---\n"
                    "Widget supports Legacy mode.\n\n"
                    "Safe mode requires firmware 2.0.\n\n"
                    "Widget is blue.\n"
                ),
            ),
        ),
        log_body="- Added the approved Safe mode firmware requirement.",
    )


def test_e2e_05_feedback_becomes_a_validated_versioned_knowledge_improvement(
    tmp_path: Path,
) -> None:
    v1_vault = copy_vault(tmp_path)
    v1_manifest = manifest(v1_vault)
    catalog = KnowledgeCatalog()
    catalog.register(v1_manifest, v1_vault)
    model = ProductKnowledgeModel(
        KnowledgeQueryRequest(asset=V1, question="What firmware does Safe mode require?")
    )
    agent, bridge = resident(tmp_path, catalog, model)
    raw_before = {name: v1_vault.read_bytes(name) for name in v1_vault.raw_files()}
    wiki_before = v1_vault.read("wiki/entities/Widget.md")

    initial = ask(agent, model, V1, "What firmware does Safe mode require?")
    assert initial.answer.text.startswith("Widget supports Legacy mode")
    assert all(passage.citation.kind == "raw" for passage in initial.cited_passages)
    assert bridge.events[-1].asset == KNOWLEDGE_QUERY_SPEC.identity

    request = capture_improvement(
        initial,
        request_id="improve-safe-mode",
        feedback="The answer omits the required firmware version.",
        expected_information="Safe mode requires firmware 2.0",
    )
    assert request.target == V1 and request.answer.trace == QUERY_TRACE
    assert request.development_approval.status == "pending"
    assert v1_vault.read("wiki/entities/Widget.md") == wiki_before
    assert {name: v1_vault.read_bytes(name) for name in v1_vault.raw_files()} == raw_before

    with pytest.raises(ValueError, match="triage approval"):
        create_candidate(
            v1_manifest,
            v1_vault,
            request,
            identity=V2,
            target_root=tmp_path / "unapproved-v2",
            plan=candidate_plan(v1_vault),
            cases=cases(),
            stamp="e2e05-unapproved",
        )
    assert not (tmp_path / "unapproved-v2").exists()
    request = authorize_improvement(
        request,
        BusinessApproval(
            status="approved",
            reviewer="knowledge-maintainer",
            evidence="Feedback is reproducible and in scope",
        ),
    )

    candidate = build_candidate(
        agent,
        model,
        KnowledgeCandidateRequest(
            base=V1,
            improvement=request,
            candidate_identity=V2,
            target_root=str((tmp_path / "candidate-v2").resolve()),
            plan=candidate_plan(v1_vault),
            cases=cases(),
            stamp="e2e05-candidate",
        ),
    )
    assert bridge.events[-1].asset == KNOWLEDGE_CANDIDATE_SPEC.identity
    candidate_vault = Vault(Path(candidate.vault_root))
    assert candidate.manifest.metadata.lifecycle == "draft"
    assert {
        name: candidate_vault.read_bytes(name) for name in candidate_vault.raw_files()
    } == raw_before
    assert candidate_vault.read("decisions.md") == v1_vault.read("decisions.md")

    evidence = validate_candidate(candidate, model=model, alias="knowledge-answerer")
    assert evidence.status == "passed"
    assert {item.case_id: item.passed for item in evidence.cases} == {
        "safe-mode-feedback": True,
        "legacy-regression": True,
    }
    log_before = candidate_vault.read_bytes("log.md")
    (candidate_vault.root / "log.md").write_bytes(log_before + b"\nexternal drift\n")
    with pytest.raises(ValueError, match="passing candidate validation"):
        approve_candidate(
            candidate,
            evidence,
            BusinessApproval(status="approved", reviewer="domain-owner", evidence="stale evidence"),
        )
    (candidate_vault.root / "log.md").write_bytes(log_before)
    approved = approve_candidate(
        candidate,
        evidence,
        BusinessApproval(
            status="approved",
            reviewer="domain-owner",
            evidence="Safe mode answer and domain regressions reviewed",
        ),
    )
    assert approved.manifest.metadata.lifecycle == "validated"
    published = publish_candidate(approved, evidence)
    assert published.metadata.lifecycle == "published"
    assert published.metadata.business_approval.reviewer == "domain-owner"
    assert published.metadata.technical_policy == v1_manifest.metadata.technical_policy
    catalog.register(published, candidate_vault)

    corrected = ask(agent, model, V2, "What firmware does Safe mode require?")
    assert "Safe mode requires firmware 2.0" in corrected.answer.text
    assert all(passage.citation.kind == "raw" for passage in corrected.cited_passages)
    assert [item.metadata.identity for item in catalog.versions("engineering", "widget-guide")] == [
        V1,
        V2,
    ]
    rollback = ask(agent, model, V1, "What firmware does Safe mode require?")
    assert rollback.answer.text == initial.answer.text
    assert {name: v1_vault.read_bytes(name) for name in v1_vault.raw_files()} == raw_before
    agent.state.close()


def test_e2e_05_unsupported_wiki_only_content_is_not_grounded(tmp_path: Path) -> None:
    vault = copy_vault(tmp_path)
    catalog = KnowledgeCatalog()
    catalog.register(manifest(vault), vault)
    model = ProductKnowledgeModel(KnowledgeQueryRequest(asset=V1, question="Is it blue?"))
    agent, _bridge = resident(tmp_path, catalog, model)
    model.routed = KnowledgeQueryRequest(asset=V1, question="Is it blue?")
    outcome = asyncio.run(
        agent.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id="bridge-company",
                namespace="engineering",
                message="Is it blue?",
                trace=QUERY_TRACE,
            )
        )
    )
    agent.state.close()
    assert outcome.capability is not None and outcome.capability.status == "failed"
    assert outcome.capability.failure is not None
    assert outcome.capability.failure.code == "knowledge_not_grounded"


def test_e2e_05_regression_failure_blocks_domain_approval(tmp_path: Path) -> None:
    vault = copy_vault(tmp_path)
    base = manifest(vault)
    good_model = ProductKnowledgeModel(
        KnowledgeQueryRequest(asset=V1, question="What firmware does Safe mode require?")
    )
    catalog = KnowledgeCatalog()
    catalog.register(base, vault)
    agent, _bridge = resident(tmp_path, catalog, good_model)
    record = ask(agent, good_model, V1, "What firmware does Safe mode require?")
    agent.state.close()
    request = capture_improvement(
        record,
        request_id="improve-regression-check",
        feedback="Missing firmware.",
        expected_information="Safe mode requires firmware 2.0",
    )
    request = authorize_improvement(
        request,
        BusinessApproval(
            status="approved", reviewer="maintainer", evidence="Reproduced from the fixture"
        ),
    )
    candidate = create_candidate(
        base,
        vault,
        request,
        identity=V2,
        target_root=tmp_path / "broken-v2",
        plan=candidate_plan(vault),
        cases=cases(),
        stamp="e2e05-broken",
    )
    broken = validate_candidate(
        candidate,
        model=RegressionBreakingModel(
            KnowledgeQueryRequest(asset=V2, question="Does it support Legacy mode?")
        ),
        alias="knowledge-answerer",
    )
    assert broken.status == "failed"
    assert broken.cases[0].passed and not broken.cases[1].passed
    with pytest.raises(ValueError, match="passing candidate validation"):
        approve_candidate(
            candidate,
            broken,
            BusinessApproval(status="approved", reviewer="owner", evidence="new case passed"),
        )


def test_e2e_05_persisted_decision_blocks_reingestion_of_rejected_claim(tmp_path: Path) -> None:
    vault = copy_vault(tmp_path)
    base = manifest(vault)
    model = ProductKnowledgeModel(
        KnowledgeQueryRequest(asset=V1, question="What firmware does Safe mode require?")
    )
    catalog = KnowledgeCatalog()
    catalog.register(base, vault)
    agent, _bridge = resident(tmp_path, catalog, model)
    record = ask(agent, model, V1, "What firmware does Safe mode require?")
    agent.state.close()
    request = capture_improvement(
        record,
        request_id="reingest-rejected",
        feedback="Restore old guidance.",
        expected_information="Turbo mode is recommended.",
    )
    request = authorize_improvement(
        request,
        BusinessApproval(
            status="approved", reviewer="maintainer", evidence="Check against decisions"
        ),
    )
    unsafe = candidate_plan(vault).model_copy(
        update={
            "pages": (
                candidate_plan(vault).pages[0],
                candidate_plan(vault)
                .pages[1]
                .model_copy(
                    update={
                        "content": candidate_plan(vault).pages[1].content
                        + "\nTurbo mode is recommended.\n"
                    }
                ),
            )
        }
    )
    decisions_before = vault.read_bytes("decisions.md")
    with pytest.raises(ValueError, match="persisted settled decision"):
        create_candidate(
            base,
            vault,
            request,
            identity=V2,
            target_root=tmp_path / "unsafe-v2",
            plan=unsafe,
            cases=cases(),
            stamp="e2e05-unsafe",
        )
    assert vault.read_bytes("decisions.md") == decisions_before
    assert not (tmp_path / "unsafe-v2").exists()


def test_e2e_05_bridge_confines_candidate_workspace(tmp_path: Path) -> None:
    vault = copy_vault(tmp_path)
    base = manifest(vault)
    catalog = KnowledgeCatalog()
    catalog.register(base, vault)
    model = ProductKnowledgeModel(
        KnowledgeQueryRequest(asset=V1, question="What firmware does Safe mode require?")
    )
    agent, _bridge = resident(tmp_path, catalog, model)
    record = ask(agent, model, V1, "What firmware does Safe mode require?")
    improvement = authorize_improvement(
        capture_improvement(
            record,
            request_id="outside-workspace",
            feedback="Missing firmware.",
            expected_information="Safe mode requires firmware 2.0",
        ),
        BusinessApproval(
            status="approved", reviewer="maintainer", evidence="Reproduced from the fixture"
        ),
    )
    outside = tmp_path.parent / f"{tmp_path.name}-outside-v2"
    model.routed = KnowledgeCandidateRequest(
        base=V1,
        improvement=improvement,
        candidate_identity=V2,
        target_root=str(outside.resolve()),
        plan=candidate_plan(vault),
        cases=cases(),
        stamp="e2e05-outside",
    )
    outcome = asyncio.run(
        agent.handle(
            LocalAgentRequest(
                ingress="local",
                actor="engineer",
                bridge_id="bridge-company",
                namespace="engineering",
                message="Prepare the approved Knowledge candidate.",
                trace=QUERY_TRACE,
            )
        )
    )
    agent.state.close()
    assert outcome.capability is not None and outcome.capability.status == "failed"
    assert outcome.capability.failure is not None
    assert outcome.capability.failure.code == "candidate_path_not_allowed"
    assert not outside.exists()
