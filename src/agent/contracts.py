"""Personal agent configuration and deterministic routing interfaces."""

from typing import Protocol

from pydantic import Field

from common.assets import AssetIdentity, AssetMetadata, RegistryContract
from common.base import Text
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


class DeterministicRouter(Protocol):
    """Resolve known routes before consulting any model; None means no known route."""

    def resolve(self, request: RequestContext) -> RouteDecision | None: ...
