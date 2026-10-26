"""Personal agent configuration and deterministic routing interfaces."""

from datetime import datetime
from typing import Literal, Protocol, Self

from pydantic import AwareDatetime, Field, model_validator

from agent.backend_contracts import MAX_CONVERSATION_TOOL_CALLS, MAX_CONVERSATION_TURNS
from common.assets import AssetIdentity, AssetMetadata, RegistryContract
from common.base import Symbol, Text
from common.execution import RequestContext, RouteDecision
from models.contracts import ModelRequirements

#: A delegated sub-run's longest wall-clock limit (the default turn budget).
MAX_DELEGATION_TIME_LIMIT_S = 1800


class AgentProfile(RegistryContract):
    metadata: AssetMetadata
    description: Text
    skills: tuple[AssetIdentity, ...] = ()
    allowed_capabilities: tuple[AssetIdentity, ...] = ()
    knowledge: tuple[AssetIdentity, ...] = ()
    may_delegate_to: tuple[AssetIdentity, ...] = ()
    policy_constraints: tuple[Text, ...] = ()
    model_requirements: ModelRequirements = ModelRequirements()
    # Bounded by the Gateway's own turn budget (owner 2026-10-19: 150 tool calls).
    max_turns: int = Field(default=8, ge=1, le=MAX_CONVERSATION_TURNS, strict=True)
    max_retries: int = Field(default=1, ge=0, le=10, strict=True)
    # Multi-agent V1 (ADR-MA2, ADR-MA3); every field has a default, so every
    # earlier profile file stays valid. Read only when the profile runs as a
    # delegated sub-agent (`agent/delegation.py`).
    # Which model a sub-agent uses: "session" is the session's own model
    # through the approved client. An alias allowlist inside the approved
    # Gateway comes later as another value; an unknown one is invalid.
    model_policy: Literal["session"] = "session"
    # The sub-run's tool cap and wall-clock limit (never above the parent
    # turn's own; `max_turns` above is its model-turn limit).
    max_tool_calls: int = Field(default=20, ge=1, le=MAX_CONVERSATION_TOOL_CALLS, strict=True)
    time_limit_s: int = Field(default=300, ge=1, le=MAX_DELEGATION_TIME_LIMIT_S, strict=True)
    # What the profile is for, shown to a parent model choosing a target.
    selector_hint: str | None = Field(default=None, min_length=1, max_length=240)

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
