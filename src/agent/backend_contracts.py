"""Provider-neutral backend discovery and conversation adapter contracts."""

from typing import Literal, Protocol, Self, TypeVar

from pydantic import Field, StrictBool, model_validator

from common.base import Contract, Symbol
from common.execution import RequestContext
from models.contracts import ModelMessage

BackendKind = Literal["model", "agent"]
BackendHarness = Literal["aep", "native"]
BackendHealthState = Literal["ready", "unknown", "unavailable"]


class BackendProfile(Contract):
    """Declared features for discovery, never an execution permission grant."""

    backend_id: Symbol
    kind: BackendKind
    harness: BackendHarness
    tools: StrictBool = False
    resume: StrictBool = False

    @model_validator(mode="after")
    def kind_matches_harness(self) -> Self:
        if self.kind == "model" and self.harness != "aep":
            raise ValueError("model backend uses the AEP harness")
        if self.kind == "agent" and self.harness != "native":
            raise ValueError("agent backend uses a native harness")
        return self


class BackendHealth(Contract):
    """Observed backend state; unknown liveness is not a policy grant."""

    backend_id: Symbol
    state: BackendHealthState
    reason: str | None = None


class GatewayConversationRequest(Contract):
    """Internal adapter input; preserves the existing Gateway call exactly."""

    context: RequestContext
    history: tuple[ModelMessage, ...]
    persona_guidance: str | None = None
    allowed_tools: tuple[Symbol, ...] | None = None
    max_turns: int = 5
    max_history_messages: int = Field(default=12, ge=1, le=40, strict=True)

    @model_validator(mode="after")
    def bounded_tool_scope(self) -> Self:
        if self.allowed_tools is not None and len(set(self.allowed_tools)) != len(
            self.allowed_tools
        ):
            raise ValueError("allowed tool names must be unique")
        if isinstance(self.max_turns, bool) or not 1 <= self.max_turns <= 5:
            raise ValueError("Gateway conversation supports one to five turns")
        return self


RequestT_contra = TypeVar("RequestT_contra", contravariant=True)
ResultT_co = TypeVar("ResultT_co", covariant=True)


class ExecutionBackend(Protocol[RequestT_contra, ResultT_co]):
    """One backend execution boundary, independent of provider SDKs."""

    @property
    def profile(self) -> BackendProfile: ...

    def health(self) -> BackendHealth: ...

    async def execute(self, request: RequestT_contra) -> ResultT_co: ...
