"""Personal agent configuration and deterministic routing interfaces."""

from datetime import datetime
from typing import Protocol, Self

from pydantic import AwareDatetime, Field, model_validator

from common.assets import AssetIdentity, AssetMetadata, RegistryContract
from common.base import Symbol, Text
from common.execution import RequestContext, RouteDecision
from models.contracts import ModelRequirements


class AgentProfile(RegistryContract):
    metadata: AssetMetadata
    description: Text
    skills: tuple[AssetIdentity, ...] = ()
    allowed_capabilities: tuple[AssetIdentity, ...] = ()
    knowledge: tuple[AssetIdentity, ...] = ()
    may_delegate_to: tuple[AssetIdentity, ...] = ()
    policy_constraints: tuple[Text, ...] = ()
    model_requirements: ModelRequirements = ModelRequirements()
    max_turns: int = Field(default=8, ge=1, le=100, strict=True)
    max_retries: int = Field(default=1, ge=0, le=10, strict=True)

    @model_validator(mode="after")
    def exact_unique_references(self) -> Self:
        for field in ("skills", "allowed_capabilities", "knowledge", "may_delegate_to"):
            keys = [item.key for item in getattr(self, field)]
            if len(keys) != len(set(keys)):
                raise ValueError(f"{field} names each exact asset once")
        return self


class ActiveAgentProfile(RegistryContract):
    """Host-local choice of one installed profile; grants no authority."""

    profile: AssetIdentity
    actor: Symbol
    activated_at: AwareDatetime

    @classmethod
    def of(cls, profile: AssetIdentity, actor: str) -> Self:
        from datetime import UTC

        return cls(profile=profile, actor=actor, activated_at=datetime.now(UTC))


class DeterministicRouter(Protocol):
    """Resolve known routes before consulting any model; None means no known route."""

    def resolve(self, request: RequestContext) -> RouteDecision | None: ...
