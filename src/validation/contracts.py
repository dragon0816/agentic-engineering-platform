"""Serializable requests and decisions for a bounded remote validation loop."""

from pathlib import PurePosixPath, PureWindowsPath
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit

from pydantic import Field, StringConstraints, field_validator, model_validator

from common.assets import AssetIdentity, RegistryContract
from common.base import Slug, Symbol, Text
from models.catalog import ModelEndpoint

GitCommit = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]


class ValidationTarget(RegistryContract):
    """The exact capability revision and deterministic test profile to validate."""

    capability: AssetIdentity
    package_commit: GitCommit
    build: Text
    test_profile: Symbol


class DeploymentArtifact(RegistryContract):
    """One immutable CI artifact Hermes may install for a pinned commit.

    This is deployment input, not a registry asset and not an authorization
    grant.  The artifact name deliberately repeats the commit so a consumer
    can reject a successful artifact that belongs to another revision.
    """

    repository: Text
    package_commit: GitCommit
    workflow_run_id: int = Field(gt=0, strict=True)
    artifact_id: int = Field(gt=0, strict=True)
    artifact_name: Text

    @model_validator(mode="after")
    def names_the_pinned_commit(self) -> Self:
        expected = f"aep-windows-preview-{self.package_commit}"
        if self.artifact_name != expected:
            raise ValueError("artifact name must identify the pinned package commit")
        return self


class ValidationExecution(RegistryContract):
    """Execution identity and declared prerequisites; this does not grant them."""

    bridge: Symbol
    actor: Symbol
    required_grants: tuple[AssetIdentity, ...] = ()
    model_routing: Symbol | None = None
    knowledge_assets: tuple[AssetIdentity, ...] = ()

    @model_validator(mode="after")
    def unique_requirements(self) -> Self:
        if len({grant.key for grant in self.required_grants}) != len(self.required_grants):
            raise ValueError("required grants must be unique")
        if len({asset.key for asset in self.knowledge_assets}) != len(self.knowledge_assets):
            raise ValueError("knowledge assets must be unique")
        return self


class ValidationRequest(RegistryContract):
    """A bounded request that Hermes can preflight and execute deterministically."""

    request_id: Symbol
    target: ValidationTarget
    execution: ValidationExecution
    acceptance_criteria: tuple[Symbol, ...]
    max_codex_repair_attempts: int = Field(ge=0, le=3, strict=True)
    max_hermes_retests: int = Field(ge=0, le=3, strict=True)

    @field_validator("acceptance_criteria")
    @classmethod
    def criteria_are_explicit(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("at least one acceptance criterion is required")
        if len(value) != len(set(value)):
            raise ValueError("acceptance criteria must be unique")
        return value


class OwnerDecision(RegistryContract):
    """A recorded decision permits Hermes to re-run preflight; it changes no grant."""

    decision_id: Symbol
    request_id: Symbol
    kind: Literal["authorize_test_actor", "configure_model_routing", "enable_knowledge_integration"]
    choice: Literal["approved", "rejected"]
    evidence: Text


def _profile_path(value: str) -> str:
    """A profile may name only a file shipped inside its own bundle directory."""
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or PureWindowsPath(value).is_absolute()
        or not value
        or ".." in path.parts
        or "\\" in value
    ):
        raise ValueError("validation fixture paths must be relative POSIX paths")
    return value


class ValidationGrantRequirement(RegistryContract):
    """The exact local grant a fixed validation profile may install for its actor."""

    asset: AssetIdentity
    permissions: tuple[Symbol, ...] = Field(min_length=1)
    policy_refs: tuple[Text, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_policy_values(self) -> Self:
        if len(self.permissions) != len(set(self.permissions)):
            raise ValueError("validation grant permissions must be unique")
        if len(self.policy_refs) != len(set(self.policy_refs)):
            raise ValueError("validation grant policies must be unique")
        return self


class LoopbackModelFixture(RegistryContract):
    """Credential-free model endpoint used only by the fixed remote proof."""

    endpoint: ModelEndpoint
    routing_alias: Symbol
    responses_path: Text

    @field_validator("responses_path")
    @classmethod
    def relative_responses_path(cls, value: str) -> str:
        return _profile_path(value)

    @model_validator(mode="after")
    def fixed_openai_compatible_loopback(self) -> Self:
        endpoint = self.endpoint
        if endpoint.provider != "openai_compatible":
            raise ValueError("validation model must use the production OpenAI-compatible adapter")
        if endpoint.alias != self.routing_alias:
            raise ValueError("validation model routing alias must name its endpoint")
        if endpoint.credential is not None:
            raise ValueError("loopback validation model carries no credential")
        if not endpoint.capabilities.local:
            raise ValueError("loopback validation model must be declared local")
        parsed = urlsplit(endpoint.base_url or "")
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("validation model endpoint must be HTTP loopback")
        return self


class SopValidationFixture(RegistryContract):
    pdf_path: Text
    namespace: Slug
    name: Symbol
    required_capabilities: tuple[AssetIdentity, ...] = Field(min_length=1)

    @field_validator("pdf_path")
    @classmethod
    def relative_pdf_path(cls, value: str) -> str:
        return _profile_path(value)


class KnowledgeValidationFixture(RegistryContract):
    asset: AssetIdentity
    manifest_template_path: Text
    vault_path: Text
    vault_ref_placeholder: Text
    question: Text

    @field_validator("manifest_template_path", "vault_path")
    @classmethod
    def relative_paths(cls, value: str) -> str:
        return _profile_path(value)


class CompanyAgentValidationProfile(RegistryContract):
    """Non-secret, allowlisted setup for the three Company Agent proof routes."""

    schema_id: Literal["aep-company-agent-integration-profile/v1"] = Field(alias="schema")
    profile: Literal["aep-company-agent-integration-v1"]
    model: LoopbackModelFixture
    grants: tuple[ValidationGrantRequirement, ...] = Field(min_length=1)
    sop: SopValidationFixture
    knowledge: KnowledgeValidationFixture
    personal_proof_fixture_path: Text
    acceptance_criteria: tuple[Symbol, ...] = Field(min_length=1)

    @field_validator("personal_proof_fixture_path")
    @classmethod
    def relative_personal_proof_path(cls, value: str) -> str:
        return _profile_path(value)

    @model_validator(mode="after")
    def unique_profile_requirements(self) -> Self:
        assets = [grant.asset.key for grant in self.grants]
        if len(assets) != len(set(assets)):
            raise ValueError("validation grants must name unique assets")
        if len(self.acceptance_criteria) != len(set(self.acceptance_criteria)):
            raise ValueError("validation acceptance criteria must be unique")
        return self
