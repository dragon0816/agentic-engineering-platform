"""Serializable requests and decisions for a bounded remote validation loop."""

from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from common.assets import AssetIdentity, RegistryContract
from common.base import Symbol, Text

GitCommit = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{40}$")]


class ValidationTarget(RegistryContract):
    """The exact capability revision and deterministic test profile to validate."""

    capability: AssetIdentity
    package_commit: GitCommit
    build: Text
    test_profile: Symbol


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
