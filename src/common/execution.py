"""Execution intent and result messages; no execution engine or authorization server."""

from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, StrictBool, StringConstraints, model_validator

from common.assets import AssetIdentity
from common.base import Contract, Slug, Symbol, Text

SideEffect = Literal["read", "write", "execute", "external_side_effect"]
RunStatus = Literal["pending", "running", "succeeded", "failed", "needs_input", "unavailable"]
IdempotencyKey = Annotated[
    str, StringConstraints(strict=True, min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$")
]


class StepAttempt(Contract):
    """Attempt metadata only; step_results retain one terminal result per step."""

    step_index: int = Field(ge=0, strict=True)
    attempt: int = Field(ge=1, le=3, strict=True)
    status: Literal["succeeded", "failed", "needs_input", "unavailable"]
    code: Symbol | None = None
    handler_invoked: StrictBool = False

    @model_validator(mode="after")
    def outcome_code(self) -> Self:
        if (self.status == "succeeded") != (self.code is None):
            raise ValueError("non-success attempts require a code; success forbids one")
        return self


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
    # Evidence for effect classification: True once the Bridge invoked the handler.
    handler_invoked: StrictBool = False

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
    resumed_from: Symbol | None = None

    @model_validator(mode="after")
    def failure_state(self) -> Self:
        failed = self.status in {"failed", "needs_input", "unavailable"}
        if failed != (self.failure is not None):
            raise ValueError("failure detail must match workflow state")
        return self


StepState = Literal["completed", "never_started", "uncertain"]


class StepStateRecord(Contract):
    """Effect classification of one declared step in a run; never payloads."""

    step_index: int = Field(ge=0, strict=True)
    state: StepState
    code: Symbol | None = None

    @model_validator(mode="after")
    def completed_without_code(self) -> Self:
        if self.state == "completed" and self.code is not None:
            raise ValueError("completed steps carry no failure code")
        return self


class ResumePolicy(Contract):
    """Trusted caller/host option, never model output or workflow metadata.

    `reject` never replays a step whose effect is uncertain; `replay_read_only`
    replays it only when the installed capability is classified `read`;
    `replay_side_effects` explicitly accepts a possible duplicate side effect.
    """

    uncertain: Literal["reject", "replay_read_only", "replay_side_effects"] = "reject"


class ResumePlan(Contract):
    """What resuming a run would redo; `next_step` is None when nothing remains."""

    run_id: Symbol
    workflow: AssetIdentity
    status: RunStatus
    steps: tuple[StepStateRecord, ...]
    next_step: int | None = None

    @model_validator(mode="after")
    def linear_progress(self) -> Self:
        if [step.step_index for step in self.steps] != list(range(len(self.steps))):
            raise ValueError("step states must be listed once each in declared order")
        remaining = [step.step_index for step in self.steps if step.state != "completed"]
        if (remaining[0] if remaining else None) != self.next_step:
            raise ValueError("next_step must be the first step that is not completed")
        return self


class ApprovalRequest(Contract):
    approval_id: Symbol
    trace: TraceIdentifiers
    asset: AssetIdentity
    requester: Symbol
    layer: Literal["business", "technical_policy", "execution"]
    reason: Text
    required_permissions: tuple[Symbol, ...] = ()
