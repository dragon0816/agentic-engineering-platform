"""Provider-neutral contracts for governed Software continuous evolution."""

from __future__ import annotations

import hashlib
from typing import Literal, Self

from pydantic import Field, JsonValue, model_validator

from common.assets import (
    AssetIdentity,
    AssetMetadata,
    BusinessApproval,
    Owner,
    RegistryContract,
)
from common.base import Sha256, Symbol, Text
from common.execution import Failure, TraceIdentifiers
from harness.contracts import ChangeRecord, CodingHarnessResult, CommandOutcome


class ExternalRepository(RegistryContract):
    provider: Literal["fixture", "github", "gitlab"]
    locator: Text
    revision: Sha256


class SoftwareInterface(RegistryContract):
    name: Symbol
    input_contract: Symbol
    output_contract: Symbol


class SoftwareRelease(RegistryContract):
    release_ref: Text
    source_revision: Sha256
    evidence_refs: tuple[Text, ...] = Field(min_length=1)
    previous_version: AssetIdentity | None = None


class SoftwareManifest(RegistryContract):
    metadata: AssetMetadata
    kind: Literal["software"] = "software"
    repository: ExternalRepository
    interfaces: tuple[SoftwareInterface, ...] = Field(min_length=1)
    release: SoftwareRelease

    @model_validator(mode="after")
    def governed_release(self) -> Self:
        names = tuple(item.name for item in self.interfaces)
        if len(names) != len(set(names)):
            raise ValueError("Software interface names must be unique")
        if self.release.source_revision != self.repository.revision:
            raise ValueError("Software release and repository revisions must match")
        if self.release.previous_version == self.metadata.identity:
            raise ValueError("Software release cannot roll back to itself")
        if self.metadata.lifecycle == "published" and (
            self.metadata.business_approval.status != "approved"
            or not self.metadata.validation_refs
            or not self.metadata.evaluation_refs
        ):
            raise ValueError("published Software requires approval and validation evidence")
        return self


class SoftwareFailureReport(RegistryContract):
    target: AssetIdentity
    trace: TraceIdentifiers
    expected_behavior: Text
    actual_behavior: Text
    evidence: tuple[Text, ...] = Field(min_length=1)
    example_input: JsonValue
    expected_output: JsonValue
    observed_output: JsonValue
    reproduction_environment: Text
    acceptance_criteria: tuple[Text, ...] = Field(min_length=1)


class SoftwareImprovementRequest(RegistryContract):
    request_id: Symbol
    target: AssetIdentity
    owner: Owner
    repository: ExternalRepository
    report: SoftwareFailureReport
    development_approval: BusinessApproval = BusinessApproval()

    @model_validator(mode="after")
    def routed_target(self) -> Self:
        if self.target != self.report.target:
            raise ValueError("Software improvement must retain the reported exact version")
        return self


class SoftwareDevelopmentRequest(RegistryContract):
    improvement: SoftwareImprovementRequest


class PullRequestCandidate(RegistryContract):
    candidate_id: Symbol
    trace: TraceIdentifiers
    target: AssetIdentity
    repository: ExternalRepository
    title: Text
    body: Text
    changes: tuple[ChangeRecord, ...] = Field(min_length=1)
    validation_sha256: Sha256
    external_write: Literal[False] = False
    merged: Literal[False] = False
    released: Literal[False] = False


class SoftwareDevelopmentResult(RegistryContract):
    trace: TraceIdentifiers
    improvement: SoftwareImprovementRequest
    status: Literal["validated", "failed", "unreproduced"]
    reproduction: CommandOutcome
    harness: CodingHarnessResult | None = None
    pull_request: PullRequestCandidate | None = None
    failure: Failure | None = None
    release_ready: Literal[False] = False
    merged: Literal[False] = False
    released: Literal[False] = False

    @model_validator(mode="after")
    def evidence_matches_status(self) -> Self:
        if self.trace != self.improvement.report.trace:
            raise ValueError("Software development must retain the report trace")
        if self.status == "validated":
            if (
                self.reproduction.status != "failed"
                or self.harness is None
                or self.harness.status != "validated"
                or self.pull_request is None
                or self.failure is not None
            ):
                raise ValueError(
                    "validated Software requires reproduction, Harness and PR evidence"
                )
            expected_validation = hashlib.sha256(
                self.harness.model_dump_json().encode("utf-8")
            ).hexdigest()
            if (
                self.pull_request.trace != self.trace
                or self.pull_request.target != self.improvement.target
                or self.pull_request.repository != self.improvement.repository
                or self.pull_request.changes != self.harness.changes
                or self.pull_request.validation_sha256 != expected_validation
            ):
                raise ValueError("PR preparation must bind the exact validated change")
        elif self.status == "unreproduced":
            if (
                self.reproduction.status != "passed"
                or self.harness is not None
                or self.pull_request is not None
                or self.failure is None
                or self.failure.code != "issue_not_reproduced"
            ):
                raise ValueError("unreproduced Software requires a passing baseline and no change")
        elif self.pull_request is not None or self.failure is None:
            raise ValueError("failed Software development cannot prepare a PR candidate")
        if self.harness is not None and self.harness.trace != self.trace:
            raise ValueError("Harness evidence must retain the report trace")
        return self


class PullRequestReview(RegistryContract):
    status: Literal["approved", "rejected"]
    reviewer: Symbol
    evidence: Text


class ReviewedPullRequest(RegistryContract):
    candidate: PullRequestCandidate
    review: PullRequestReview

    @model_validator(mode="after")
    def approved(self) -> Self:
        if self.review.status != "approved":
            raise ValueError("merge preparation requires an approved source-control review")
        return self


class MergeRecord(RegistryContract):
    candidate_sha256: Sha256
    candidate_id: Symbol
    target: AssetIdentity
    repository: ExternalRepository
    merged_revision: Sha256
    reviewed_by: Symbol
    review_evidence: Text
    merged_by: Symbol
    evidence_ref: Text

    @model_validator(mode="after")
    def new_revision(self) -> Self:
        if self.repository.revision == self.merged_revision:
            raise ValueError("merge evidence must identify a new repository revision")
        return self


class ReleaseRecord(RegistryContract):
    identity: AssetIdentity
    previous_version: AssetIdentity
    repository: ExternalRepository
    release_ref: Text
    merge: MergeRecord
    released_by: Symbol
    evidence_ref: Text

    @model_validator(mode="after")
    def release_lineage(self) -> Self:
        if (
            self.identity.namespace != self.previous_version.namespace
            or self.identity.name != self.previous_version.name
            or self.identity.version == self.previous_version.version
        ):
            raise ValueError("release identity must be a new version of the same Software")
        if self.repository.revision != self.merge.merged_revision:
            raise ValueError("release must identify the merged repository revision")
        return self


class SoftwareCatalog:
    """Exact published Software metadata; source remains in external repositories."""

    def __init__(self) -> None:
        self._versions: dict[tuple[str, str, str], SoftwareManifest] = {}

    def register(self, manifest: SoftwareManifest) -> None:
        checked = SoftwareManifest.model_validate(manifest)
        if checked.metadata.lifecycle != "published":
            raise ValueError("only published Software enters the catalog")
        if checked.metadata.identity.key in self._versions:
            raise ValueError("Software version already registered")
        previous = checked.release.previous_version
        if previous is not None:
            prior = self._versions.get(previous.key)
            if prior is None:
                raise ValueError("Software rollback version must already be registered")
            if (
                prior.repository.provider != checked.repository.provider
                or prior.repository.locator != checked.repository.locator
                or prior.repository.revision == checked.repository.revision
            ):
                raise ValueError("Software release lineage must retain its repository and advance")
        self._versions[checked.metadata.identity.key] = checked

    def get(self, identity: AssetIdentity) -> SoftwareManifest | None:
        return self._versions.get(identity.key)

    def versions(self, namespace: str, name: str) -> tuple[SoftwareManifest, ...]:
        return tuple(
            manifest
            for key, manifest in sorted(self._versions.items())
            if key[:2] == (namespace, name)
        )


def capture_improvement(
    catalog: SoftwareCatalog, report: SoftwareFailureReport, *, request_id: str
) -> SoftwareImprovementRequest:
    checked = SoftwareFailureReport.model_validate(report)
    manifest = catalog.get(checked.target)
    if manifest is None:
        raise LookupError("Software version not found")
    return SoftwareImprovementRequest(
        request_id=request_id,
        target=checked.target,
        owner=manifest.metadata.owner,
        repository=manifest.repository,
        report=checked,
    )


def approve_improvement(
    request: SoftwareImprovementRequest, approval: BusinessApproval
) -> SoftwareImprovementRequest:
    checked = BusinessApproval.model_validate(approval)
    if checked.status != "approved":
        raise ValueError("Software development requires owner approval")
    return request.model_copy(update={"development_approval": checked})


def candidate_digest(candidate: PullRequestCandidate) -> str:
    return hashlib.sha256(candidate.model_dump_json().encode("utf-8")).hexdigest()


def approve_pull_request(
    candidate: PullRequestCandidate, review: PullRequestReview
) -> ReviewedPullRequest:
    return ReviewedPullRequest(candidate=candidate, review=review)


def record_merge(
    reviewed: ReviewedPullRequest,
    *,
    merged_revision: str,
    merged_by: str,
    evidence_ref: str,
) -> MergeRecord:
    checked = ReviewedPullRequest.model_validate(reviewed)
    return MergeRecord(
        candidate_sha256=candidate_digest(checked.candidate),
        candidate_id=checked.candidate.candidate_id,
        target=checked.candidate.target,
        repository=checked.candidate.repository,
        merged_revision=merged_revision,
        reviewed_by=checked.review.reviewer,
        review_evidence=checked.review.evidence,
        merged_by=merged_by,
        evidence_ref=evidence_ref,
    )


def record_release(
    base: SoftwareManifest,
    merge: MergeRecord,
    *,
    identity: AssetIdentity,
    release_ref: str,
    released_by: str,
    evidence_ref: str,
) -> ReleaseRecord:
    checked_base = SoftwareManifest.model_validate(base)
    checked_merge = MergeRecord.model_validate(merge)
    if (
        checked_merge.target != checked_base.metadata.identity
        or checked_merge.repository.provider != checked_base.repository.provider
        or checked_merge.repository.locator != checked_base.repository.locator
        or checked_merge.repository.revision != checked_base.repository.revision
    ):
        raise ValueError("merge does not descend from the published Software revision")
    repository = checked_base.repository.model_copy(
        update={"revision": checked_merge.merged_revision}
    )
    return ReleaseRecord(
        identity=identity,
        previous_version=checked_base.metadata.identity,
        repository=repository,
        release_ref=release_ref,
        merge=checked_merge,
        released_by=released_by,
        evidence_ref=evidence_ref,
    )


def publish_software(
    base: SoftwareManifest,
    release: ReleaseRecord,
    approval: BusinessApproval,
) -> SoftwareManifest:
    checked_base = SoftwareManifest.model_validate(base)
    checked_release = ReleaseRecord.model_validate(release)
    checked_approval = BusinessApproval.model_validate(approval)
    if checked_approval.status != "approved":
        raise ValueError("Software republish requires owner approval")
    if checked_release.previous_version != checked_base.metadata.identity:
        raise ValueError("Software release does not replace the supplied base version")
    release_digest = hashlib.sha256(checked_release.model_dump_json().encode("utf-8")).hexdigest()
    validation_ref = f"software-release:{release_digest}"
    metadata = checked_base.metadata.model_copy(
        update={
            "identity": checked_release.identity,
            "lifecycle": "published",
            "business_approval": checked_approval,
            "validation_refs": (*checked_base.metadata.validation_refs, validation_ref),
        }
    )
    return SoftwareManifest(
        metadata=metadata,
        repository=checked_release.repository,
        interfaces=checked_base.interfaces,
        release=SoftwareRelease(
            release_ref=checked_release.release_ref,
            source_revision=checked_release.repository.revision,
            evidence_refs=(
                checked_release.merge.evidence_ref,
                checked_release.evidence_ref,
                validation_ref,
            ),
            previous_version=checked_base.metadata.identity,
        ),
    )
