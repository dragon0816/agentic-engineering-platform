"""Execution intent and result messages; no execution engine or authorization server."""

from typing import Literal, Self

from pydantic import Field, JsonValue, StrictBool, model_validator

from common.assets import AssetIdentity
from common.base import Contract, Slug, Symbol, Text

SideEffect = Literal["read", "write", "execute", "external_side_effect"]
RunStatus = Literal["pending", "running", "succeeded", "failed", "needs_input", "unavailable"]


class TraceIdentifiers(Contract):
    trace_id: Symbol
    request_id: Symbol
    span_id: Symbol
    parent_span_id: Symbol | None = None


class AttachmentRef(Contract):
    """Opaque channel-neutral attachment metadata; resolution belongs to the Bridge."""

    file_id: Symbol
    filename: Text
    resource_ref: Symbol
    size_bytes: int = Field(ge=0, strict=True)
    media_type: Text


class RequestContext(Contract):
    trace: TraceIdentifiers
    actor: Symbol
    namespace: Slug
    message: Text
    channel: Symbol
    session_id: Symbol | None = None
    attachments: tuple[AttachmentRef, ...] = ()


class RouteDecision(Contract):
    kind: Literal["capability", "workflow", "agent", "needs_input"]
    target: AssetIdentity | None = None
    reason: Text

    @model_validator(mode="after")
    def target_consistency(self) -> Self:
        if (self.kind == "needs_input") != (self.target is None):
            raise ValueError("resolved routes require a target; needs_input has none")
        return self


class ExecutionAuthorization(Contract):
    """Execution-environment decision, distinct from all publication/review metadata."""

    allowed: StrictBool = False
    actor: Symbol | None = None
    asset: AssetIdentity | None = None
    trace: TraceIdentifiers | None = None
    policy_ref: Text | None = None

    @model_validator(mode="after")
    def explicit_grant(self) -> Self:
        if self.allowed and any(
            value is None for value in (self.actor, self.asset, self.trace, self.policy_ref)
        ):
            raise ValueError("allow requires explicit actor, asset, trace and runtime policy")
        return self


class Failure(Contract):
    code: Symbol
    message: Text
    retryable: StrictBool = False


class CapabilityResult(Contract):
    trace: TraceIdentifiers
    status: Literal["succeeded", "failed", "needs_input", "unavailable"]
    data: JsonValue = None
    failure: Failure | None = None
    warnings: tuple[Text, ...] = ()

    @model_validator(mode="after")
    def result_consistency(self) -> Self:
        if (self.status == "succeeded") != (self.failure is None):
            raise ValueError("non-success results require failure details; success forbids them")
        return self


class WorkflowRun(Contract):
    run_id: Symbol
    workflow: AssetIdentity
    trace: TraceIdentifiers
    status: RunStatus
    completed_steps: int = Field(default=0, ge=0, strict=True)
    failure: Failure | None = None

    @model_validator(mode="after")
    def failure_state(self) -> Self:
        failed = self.status in {"failed", "needs_input", "unavailable"}
        if failed != (self.failure is not None):
            raise ValueError("failure detail must match workflow state")
        return self


class ApprovalRequest(Contract):
    approval_id: Symbol
    trace: TraceIdentifiers
    asset: AssetIdentity
    requester: Symbol
    layer: Literal["business", "technical_policy", "execution"]
    reason: Text
    required_permissions: tuple[Symbol, ...] = ()
