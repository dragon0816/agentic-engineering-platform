"""Scoped assets, governance and explicit execution dependency metadata."""

import re
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StrictStr, field_validator, model_validator

from common.base import Contract, Sha256, Slug, Symbol, Text

SEMVER = re.compile(
    r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
    r"(?:-((?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)"
    r"(?:\.(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?",
    re.ASCII,
)
SECRET_PATTERN = re.compile(
    r"(?:password|api[_-]?key|access[_-]?token|secret[_-]?value)\s*[=:]\s*\S+"
    r"|\bBearer\s+\S+|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----",
    re.IGNORECASE,
)


def reject_embedded_secrets(value: object) -> None:
    """Reject recognizable credential material without echoing it in our errors."""
    if isinstance(value, str) and SECRET_PATTERN.search(value):
        raise ValueError("asset text must not contain credentials; declare a SecretRef")
    if isinstance(value, dict):
        for item in value.values():
            reject_embedded_secrets(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            reject_embedded_secrets(item)


class RegistryContract(Contract):
    @model_validator(mode="after")
    def no_embedded_credentials(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class AssetIdentity(Contract):
    namespace: Slug
    name: Slug
    version: Text

    @field_validator("version")
    @classmethod
    def semantic_version(cls, value: str) -> str:
        if not SEMVER.fullmatch(value):
            raise ValueError("version must be a full semantic version")
        return value

    @property
    def key(self) -> tuple[str, str, str]:
        return self.namespace, self.name, self.version


class Owner(Contract):
    type: Literal["user", "team", "organization", "service"]
    id: Symbol


class Review(Contract):
    status: Literal["pending", "approved", "rejected", "not_required"] = "pending"
    reviewer: Symbol | None = None
    evidence: Text | None = None

    @model_validator(mode="after")
    def decision_evidence(self) -> Self:
        if self.status != "pending" and (self.reviewer is None or self.evidence is None):
            raise ValueError("review decisions require reviewer and evidence")
        return self


class BusinessApproval(Review):
    """Domain correctness review; never grants runtime permission."""


class TechnicalPolicy(Review):
    risk: Literal["low", "medium", "high", "critical"] = "low"
    approval_required: StrictBool = True
    required_permissions: tuple[Symbol, ...] = ()
    policy_refs: tuple[Text, ...] = ()
    assessment: Literal["manual", "automated"] = "manual"

    @model_validator(mode="after")
    def privileged_review(self) -> Self:
        if self.risk in {"high", "critical"} and not self.approval_required:
            raise ValueError("high-risk capabilities require an explicit approval policy")
        if self.approval_required and self.status == "not_required":
            raise ValueError("required technical approval cannot be marked not_required")
        return self


class SecretRef(Contract):
    """Symbolic requirement; no value or backend fields are accepted."""

    name: Symbol


class CentralService(Contract):
    name: Symbol
    required: StrictBool


class ExecutionDependencies(Contract):
    local_capabilities: tuple[Symbol, ...] = ()
    central_services: tuple[CentralService, ...] = ()
    central_required: StrictBool

    @model_validator(mode="after")
    def explicit_connectivity(self) -> Self:
        if self.central_required != any(service.required for service in self.central_services):
            raise ValueError("central_required must match required central services")
        names = [service.name for service in self.central_services]
        if len(names) != len(set(names)):
            raise ValueError("central service names must be unique")
        if len(self.local_capabilities) != len(set(self.local_capabilities)):
            raise ValueError("local capability names must be unique")
        return self


class ExecutionLocation(Contract):
    mode: Literal["local", "central"]


class Provenance(Contract):
    source: Text
    revision: Text | None = None
    author: Symbol | None = None


class Compatibility(Contract):
    contract_version: Literal["1"] = "1"
    runtime: Text | None = None
    bridge: Text | None = None
    platforms: tuple[Text, ...] = ()


class PackageMetadata(Contract):
    artifact_ref: Text
    sha256: Sha256


class AssetMetadata(RegistryContract):
    identity: AssetIdentity
    owner: Owner
    visibility: Literal["private", "team", "organization", "public"]
    lifecycle: Literal["draft", "validated", "published", "deprecated"] = "draft"
    contributors: tuple[Symbol, ...] = ()
    provenance: tuple[Provenance, ...] = ()
    dependencies: tuple[AssetIdentity, ...] = ()
    compatibility: Compatibility = Compatibility()
    business_approval: BusinessApproval = BusinessApproval()
    technical_policy: TechnicalPolicy = TechnicalPolicy()
    validation_refs: tuple[Text, ...] = ()
    evaluation_refs: tuple[Text, ...] = ()
    package: PackageMetadata | None = None
    deprecation_reason: Text | None = None
    replacement: AssetIdentity | None = None

    @model_validator(mode="after")
    def deprecation(self) -> Self:
        if self.lifecycle == "deprecated" and self.deprecation_reason is None:
            raise ValueError("deprecated assets require a reason")
        if self.replacement == self.identity:
            raise ValueError("an asset cannot replace itself")
        return self


class ExecutableManifest(RegistryContract):
    metadata: AssetMetadata
    description: Text
    execution: ExecutionLocation
    dependencies: ExecutionDependencies
    secrets: tuple[SecretRef, ...] = ()
    input_contract: Symbol
    output_contract: Symbol

    @model_validator(mode="after")
    def execution_consistency(self) -> Self:
        if self.execution.mode == "central" and not self.dependencies.central_required:
            raise ValueError("central execution must declare its required central service")
        if len({ref.name for ref in self.secrets}) != len(self.secrets):
            raise ValueError("secret requirements must be unique")
        return self


class TaskManifest(ExecutableManifest):
    kind: Literal["task"] = "task"
    capability: AssetIdentity


PathPart = StrictStr | Annotated[int, Field(ge=0, strict=True)]


class RunInput(Contract):
    """Select an exact path in this run's arguments; empty path selects the root."""

    source: Literal["run"]
    path: tuple[PathPart, ...] = ()


class StepInput(Contract):
    """Select only validated data from an earlier, successful step in this run."""

    source: Literal["step"]
    step_index: int = Field(ge=0, strict=True)
    path: tuple[PathPart, ...] = ()


class WorkflowStep(RegistryContract):
    capability: AssetIdentity
    inputs: dict[Symbol, Annotated[RunInput | StepInput, Field(discriminator="source")]]


class WorkflowManifest(ExecutableManifest):
    kind: Literal["workflow"] = "workflow"
    steps: tuple[AssetIdentity | WorkflowStep, ...]

    @field_validator("steps")
    @classmethod
    def nonempty_steps(
        cls, value: tuple[AssetIdentity | WorkflowStep, ...]
    ) -> tuple[AssetIdentity | WorkflowStep, ...]:
        if not value:
            raise ValueError("a workflow must declare at least one step")
        for index, step in enumerate(value):
            if isinstance(step, WorkflowStep) and any(
                isinstance(ref, StepInput) and ref.step_index >= index
                for ref in step.inputs.values()
            ):
                raise ValueError("step inputs may reference only earlier steps")
        return value
