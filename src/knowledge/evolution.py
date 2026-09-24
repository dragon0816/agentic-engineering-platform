"""Governed Knowledge improvement from grounded feedback to versioned publication."""

from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, StrictBool, field_validator, model_validator

from common.assets import (
    AssetIdentity,
    AssetMetadata,
    BusinessApproval,
    RegistryContract,
    reject_embedded_secrets,
)
from common.base import Contract, Sha256, Slug, Symbol, Text
from common.execution import TraceIdentifiers
from knowledge.query import Answer, Passage, QueryEngine, cited_numbers
from knowledge.vault import Vault, WritePlan
from models.contracts import ModelClient


def _digest(parts: list[tuple[str, bytes]]) -> str:
    value = hashlib.sha256()
    for name, data in sorted(parts):
        value.update(name.encode("utf-8"))
        value.update(b"\0")
        value.update(data)
        value.update(b"\0")
    return value.hexdigest()


def raw_digest(vault: Vault) -> str:
    root = vault.root.resolve()
    parts: list[tuple[str, bytes]] = []
    for path in sorted((root / "raw").rglob("*")):
        if not path.is_file():
            continue
        resolved = path.resolve()
        try:
            name = resolved.relative_to(root).as_posix()
        except ValueError as error:
            raise ValueError("Raw evidence must remain inside the vault") from error
        parts.append((name, resolved.read_bytes()))
    return _digest(parts)


def decision_digest(vault: Vault) -> str:
    return hashlib.sha256(vault.read_bytes("decisions.md")).hexdigest()


def knowledge_digest(vault: Vault) -> str:
    root = vault.root.resolve()
    names = [*vault.raw_files(), *vault.wiki_files()]
    names.extend(name for name in ("index.md", "log.md", "decisions.md") if vault.exists(name))
    return _digest([(name, (root / name).read_bytes()) for name in names])


class KnowledgeManifest(RegistryContract):
    metadata: AssetMetadata
    kind: Literal["knowledge"] = "knowledge"
    domain: Slug
    vault_ref: Text
    raw_sha256: Sha256
    decisions_sha256: Sha256
    content_sha256: Sha256
    evaluation_case_ids: tuple[Symbol, ...] = ()

    @model_validator(mode="after")
    def governed_version(self) -> Self:
        if len(self.evaluation_case_ids) != len(set(self.evaluation_case_ids)):
            raise ValueError("Knowledge evaluation case identities must be unique")
        if self.metadata.lifecycle == "published" and (
            self.metadata.business_approval.status != "approved"
            or not self.metadata.validation_refs
        ):
            raise ValueError("published Knowledge requires domain approval and validation")
        expected_refs = tuple(f"knowledge-case:{case_id}" for case_id in self.evaluation_case_ids)
        if (
            self.metadata.lifecycle == "published"
            and self.metadata.evaluation_refs != expected_refs
        ):
            raise ValueError("published Knowledge must reference its exact evaluation set")
        return self


class KnowledgeQueryRequest(Contract):
    asset: AssetIdentity
    question: Text

    @model_validator(mode="after")
    def safe_question(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class KnowledgeAnswerRecord(Contract):
    asset: AssetIdentity
    trace: TraceIdentifiers
    answer: Answer
    cited_passages: tuple[Passage, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def raw_grounding(self) -> Self:
        if self.answer.status != "answered" or not self.answer.text.strip():
            raise ValueError("a grounded record requires an answered query")
        if any(passage.citation.kind != "raw" for passage in self.cited_passages):
            raise ValueError("grounded claims require Raw evidence")
        numbers = cited_numbers(self.answer.text)
        expected = tuple(
            passage for number, passage in enumerate(self.answer.passages, 1) if number in numbers
        )
        if self.cited_passages != expected:
            raise ValueError("grounding must contain the exact cited passages")
        sentences = [
            sentence.strip()
            for sentence in re.split(r"(?<=[.!?])\s+", self.answer.text)
            if sentence.strip()
        ]
        if any(not cited_numbers(sentence) for sentence in sentences):
            raise ValueError("every answer sentence must cite Raw evidence")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class KnowledgeImprovementRequest(Contract):
    request_id: Symbol
    target: AssetIdentity
    answer: KnowledgeAnswerRecord
    feedback: Text
    expected_information: Text
    reproduction: Text
    acceptance_criteria: tuple[Text, ...] = Field(min_length=1)
    development_approval: BusinessApproval = BusinessApproval()

    @model_validator(mode="after")
    def linked_evidence(self) -> Self:
        if self.target != self.answer.asset:
            raise ValueError("improvement target must be the answered Knowledge version")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class KnowledgeEvaluationCase(Contract):
    case_id: Symbol
    kind: Literal["new", "regression"]
    question: Text
    required_facts: tuple[Text, ...] = Field(min_length=1)
    forbidden_facts: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def safe_expectations(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class KnowledgeCandidate(Contract):
    base: AssetIdentity
    manifest: KnowledgeManifest
    vault_root: Text
    request: KnowledgeImprovementRequest
    cases: tuple[KnowledgeEvaluationCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def candidate_shape(self) -> Self:
        if self.request.target != self.base:
            raise ValueError("candidate request must target its base version")
        identity = self.manifest.metadata.identity
        if identity.namespace != self.base.namespace or identity.name != self.base.name:
            raise ValueError("candidate must preserve the scoped Knowledge identity")
        if identity.version == self.base.version:
            raise ValueError("candidate must have a new version")
        if self.manifest.metadata.lifecycle not in {"draft", "validated"}:
            raise ValueError("a candidate is draft or validated, never published")
        ids = tuple(case.case_id for case in self.cases)
        if ids != self.manifest.evaluation_case_ids:
            raise ValueError("candidate manifest must name the exact evaluation set")
        if not any(case.kind == "new" for case in self.cases):
            raise ValueError("candidate requires the new feedback case")
        if not any(case.kind == "regression" for case in self.cases):
            raise ValueError("candidate requires existing regressions")
        return self


class KnowledgeCandidateRequest(Contract):
    base: AssetIdentity
    improvement: KnowledgeImprovementRequest
    candidate_identity: AssetIdentity
    target_root: Text
    plan: WritePlan
    cases: tuple[KnowledgeEvaluationCase, ...] = Field(min_length=1)
    stamp: Text

    @field_validator("target_root")
    @classmethod
    def absolute_target(cls, value: str) -> str:
        if not Path(value).is_absolute():
            raise ValueError("candidate target root must be absolute")
        return value

    @model_validator(mode="after")
    def safe_candidate_request(self) -> Self:
        if self.base != self.improvement.target:
            raise ValueError("candidate request must use the improvement target as its base")
        if (
            self.candidate_identity.namespace != self.base.namespace
            or self.candidate_identity.name != self.base.name
            or self.candidate_identity.version == self.base.version
        ):
            raise ValueError("candidate identity must be a new version of the base Knowledge")
        case_ids = tuple(case.case_id for case in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("candidate evaluation case identities must be unique")
        if not any(case.kind == "new" for case in self.cases):
            raise ValueError("candidate requires the new feedback case")
        if not any(case.kind == "regression" for case in self.cases):
            raise ValueError("candidate requires existing regressions")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class KnowledgeCaseResult(Contract):
    case_id: Symbol
    passed: StrictBool
    answer: KnowledgeAnswerRecord | None = None
    missing_facts: tuple[Text, ...] = ()
    present_forbidden_facts: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def result_evidence(self) -> Self:
        if self.passed != (
            self.answer is not None and not self.missing_facts and not self.present_forbidden_facts
        ):
            raise ValueError("Knowledge case status must match its evidence")
        return self


class KnowledgeValidationEvidence(Contract):
    candidate: AssetIdentity
    status: Literal["passed", "failed"]
    raw_before: Sha256
    raw_after: Sha256
    content_sha256: Sha256
    cases: tuple[KnowledgeCaseResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validation_gate(self) -> Self:
        case_ids = tuple(case.case_id for case in self.cases)
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("Knowledge validation case identities must be unique")
        passed = self.raw_before == self.raw_after and all(case.passed for case in self.cases)
        if (self.status == "passed") != passed:
            raise ValueError("Knowledge validation status must match Raw and case evidence")
        return self


def grounded_record(
    asset: AssetIdentity, trace: TraceIdentifiers, answer: Answer
) -> KnowledgeAnswerRecord:
    numbers = cited_numbers(answer.text)
    passages = tuple(
        passage for number, passage in enumerate(answer.passages, 1) if number in numbers
    )
    return KnowledgeAnswerRecord(
        asset=asset,
        trace=trace,
        answer=answer,
        cited_passages=passages,
    )


def capture_improvement(
    answer: KnowledgeAnswerRecord,
    *,
    request_id: str,
    feedback: str,
    expected_information: str,
) -> KnowledgeImprovementRequest:
    return KnowledgeImprovementRequest(
        request_id=request_id,
        target=answer.asset,
        answer=answer,
        feedback=feedback,
        expected_information=expected_information,
        reproduction=f"Ask the exact question: {answer.answer.question}",
        acceptance_criteria=(
            f"The answer states: {expected_information}",
            "Every answer sentence cites immutable Raw evidence",
            "All existing domain evaluation cases still pass",
        ),
    )


def authorize_improvement(
    request: KnowledgeImprovementRequest, approval: BusinessApproval
) -> KnowledgeImprovementRequest:
    checked = BusinessApproval.model_validate(approval)
    if checked.status != "approved":
        raise ValueError("candidate development requires an approved triage decision")
    return request.model_copy(update={"development_approval": checked})


def rejected_claims(vault: Vault) -> tuple[str, ...]:
    return tuple(
        line.partition(":")[2].strip()
        for line in vault.read("decisions.md").splitlines()
        if line.strip().casefold().startswith("- reject:") and line.partition(":")[2].strip()
    )


def create_candidate(
    base: KnowledgeManifest,
    base_vault: Vault,
    request: KnowledgeImprovementRequest,
    *,
    identity: AssetIdentity,
    target_root: Path,
    plan: WritePlan,
    cases: tuple[KnowledgeEvaluationCase, ...],
    stamp: str,
) -> KnowledgeCandidate:
    checked = KnowledgeCandidateRequest(
        base=base.metadata.identity,
        improvement=request,
        candidate_identity=identity,
        target_root=str(target_root),
        plan=plan,
        cases=cases,
        stamp=stamp,
    )
    target_root = Path(checked.target_root)
    if request.target != base.metadata.identity:
        raise ValueError("improvement request targets another Knowledge version")
    if request.development_approval.status != "approved":
        raise ValueError("candidate development requires triage approval")
    if Path(base.vault_ref).resolve() != base_vault.root.resolve():
        raise ValueError("base manifest names another vault")
    if (
        raw_digest(base_vault) != base.raw_sha256
        or decision_digest(base_vault) != base.decisions_sha256
        or knowledge_digest(base_vault) != base.content_sha256
    ):
        raise ValueError("published base Knowledge has drifted")
    folded_pages = "\n".join(page.content for page in plan.pages).casefold()
    if any(claim.casefold() in folded_pages for claim in rejected_claims(base_vault)):
        raise ValueError("candidate conflicts with a persisted settled decision")
    if target_root.exists():
        raise ValueError("candidate root already exists")
    before = raw_digest(base_vault)
    try:
        shutil.copytree(base_vault.root, target_root)
        candidate_vault = Vault(target_root)
        outcome = candidate_vault.apply(plan, mode="apply", stamp=stamp)
        if not outcome.accepted:
            raise ValueError("candidate write plan was rejected")
        after = raw_digest(candidate_vault)
        if before != after:
            raise ValueError("candidate changed immutable Raw evidence")
    except Exception:
        if target_root.exists():
            shutil.rmtree(target_root)
        raise
    metadata = base.metadata.model_copy(
        update={
            "identity": identity,
            "lifecycle": "draft",
            "business_approval": BusinessApproval(),
            "validation_refs": (),
        }
    )
    manifest = KnowledgeManifest(
        metadata=metadata,
        domain=base.domain,
        vault_ref=str(target_root.resolve()),
        raw_sha256=after,
        decisions_sha256=decision_digest(candidate_vault),
        content_sha256=knowledge_digest(candidate_vault),
        evaluation_case_ids=tuple(case.case_id for case in cases),
    )
    return KnowledgeCandidate(
        base=base.metadata.identity,
        manifest=manifest,
        vault_root=str(target_root.resolve()),
        request=request,
        cases=cases,
    )


def validate_candidate(
    candidate: KnowledgeCandidate,
    *,
    model: ModelClient,
    alias: Symbol,
) -> KnowledgeValidationEvidence:
    vault = Vault(Path(candidate.vault_root))
    current_content = knowledge_digest(vault)
    if current_content != candidate.manifest.content_sha256:
        raise ValueError("candidate content changed after creation")
    results: list[KnowledgeCaseResult] = []
    for position, case in enumerate(candidate.cases, 1):
        trace = TraceIdentifiers(
            trace_id=f"knowledge-eval-{candidate.manifest.metadata.identity.version}",
            request_id=f"case-{position}",
            span_id=case.case_id,
        )
        try:
            answer = grounded_record(
                candidate.manifest.metadata.identity,
                trace,
                QueryEngine(vault, model, alias=alias).ask(case.question, trace=trace),
            )
        except ValueError:
            results.append(
                KnowledgeCaseResult(
                    case_id=case.case_id,
                    passed=False,
                    missing_facts=case.required_facts,
                )
            )
            continue
        text = answer.answer.text.casefold()
        missing = tuple(fact for fact in case.required_facts if fact.casefold() not in text)
        forbidden = tuple(fact for fact in case.forbidden_facts if fact.casefold() in text)
        results.append(
            KnowledgeCaseResult(
                case_id=case.case_id,
                passed=not missing and not forbidden,
                answer=answer,
                missing_facts=missing,
                present_forbidden_facts=forbidden,
            )
        )
    raw_after = raw_digest(vault)
    raw_before = candidate.manifest.raw_sha256
    return KnowledgeValidationEvidence(
        candidate=candidate.manifest.metadata.identity,
        status=(
            "passed"
            if raw_before == raw_after and all(item.passed for item in results)
            else "failed"
        ),
        raw_before=raw_before,
        raw_after=raw_after,
        content_sha256=current_content,
        cases=tuple(results),
    )


def _evidence_matches(candidate: KnowledgeCandidate, evidence: KnowledgeValidationEvidence) -> bool:
    expected_cases = tuple(case.case_id for case in candidate.cases)
    observed_cases = tuple(case.case_id for case in evidence.cases)
    return (
        evidence.candidate == candidate.manifest.metadata.identity
        and evidence.content_sha256 == candidate.manifest.content_sha256
        and knowledge_digest(Vault(Path(candidate.vault_root))) == evidence.content_sha256
        and evidence.status == "passed"
        and observed_cases == expected_cases
    )


def approve_candidate(
    candidate: KnowledgeCandidate,
    evidence: KnowledgeValidationEvidence,
    approval: BusinessApproval,
) -> KnowledgeCandidate:
    checked = BusinessApproval.model_validate(approval)
    if not _evidence_matches(candidate, evidence):
        raise ValueError("domain approval requires passing candidate validation")
    if checked.status != "approved":
        raise ValueError("domain owner must approve the candidate")
    metadata = candidate.manifest.metadata.model_copy(
        update={"lifecycle": "validated", "business_approval": checked}
    )
    return candidate.model_copy(
        update={"manifest": candidate.manifest.model_copy(update={"metadata": metadata})}
    )


def publish_candidate(
    candidate: KnowledgeCandidate, evidence: KnowledgeValidationEvidence
) -> KnowledgeManifest:
    if candidate.manifest.metadata.lifecycle != "validated":
        raise ValueError("publication requires separate domain approval")
    if not _evidence_matches(candidate, evidence):
        raise ValueError("publication requires passing validation evidence")
    validation_ref = (
        "knowledge-eval:" + hashlib.sha256(evidence.model_dump_json().encode("utf-8")).hexdigest()
    )
    metadata = candidate.manifest.metadata.model_copy(
        update={
            "lifecycle": "published",
            "validation_refs": (*candidate.manifest.metadata.validation_refs, validation_ref),
            "evaluation_refs": tuple(f"knowledge-case:{case.case_id}" for case in candidate.cases),
        }
    )
    return candidate.manifest.model_copy(update={"metadata": metadata})


class KnowledgeCatalog:
    """Exact published versions and local vaults; no production Registry/database."""

    def __init__(self) -> None:
        self._versions: dict[tuple[str, str, str], tuple[KnowledgeManifest, Vault]] = {}

    def register(self, manifest: KnowledgeManifest, vault: Vault) -> None:
        checked = KnowledgeManifest.model_validate(manifest)
        if checked.metadata.lifecycle != "published":
            raise ValueError("only published Knowledge enters the query catalog")
        if raw_digest(vault) != checked.raw_sha256:
            raise ValueError("Knowledge manifest does not match its Raw evidence")
        if decision_digest(vault) != checked.decisions_sha256:
            raise ValueError("Knowledge manifest does not match its decisions")
        if knowledge_digest(vault) != checked.content_sha256:
            raise ValueError("Knowledge manifest does not match its content")
        if Path(checked.vault_ref).resolve() != vault.root.resolve():
            raise ValueError("Knowledge manifest must name the registered vault")
        if checked.metadata.identity.key in self._versions:
            raise ValueError("Knowledge version already registered")
        self._versions[checked.metadata.identity.key] = (checked, vault)

    def get(self, identity: AssetIdentity) -> tuple[KnowledgeManifest, Vault] | None:
        return self._versions.get(identity.key)

    def versions(self, namespace: str, name: str) -> tuple[KnowledgeManifest, ...]:
        return tuple(
            item[0] for key, item in sorted(self._versions.items()) if key[:2] == (namespace, name)
        )
