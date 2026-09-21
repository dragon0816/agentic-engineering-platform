"""Execution-plane checkpoint evidence; no payloads, policy grants or storage backend."""

from typing import Literal, Self

from pydantic import Field, model_validator

from common.assets import WorkflowManifest
from common.base import Contract, Sha256, Slug, Symbol
from common.execution import IdempotencyKey, ResumePlan, RunId, StepStateRecord, TraceIdentifiers


class CheckpointOwner(Contract):
    actor: Symbol
    namespace: Slug


class PayloadRef(Contract):
    """Opaque protected local data reference, not a URL, secret or access grant."""

    ref_id: Symbol
    sha256: Sha256
    contract: Symbol


class StepCheckpoint(Contract):
    step_index: int = Field(ge=0, strict=True)
    state: Literal["never_started", "started", "completed"] = "never_started"
    result: PayloadRef | None = None
    code: Symbol | None = None

    @model_validator(mode="after")
    def evidence(self) -> Self:
        if (self.state == "completed") != (self.result is not None):
            raise ValueError("only completed steps require a validated result reference")
        if self.state != "started" and self.code is not None:
            raise ValueError("only unresolved started steps may retain a failure code")
        return self


class RunCheckpoint(Contract):
    """Versioned restart evidence; trusted coordinator supplies the intent digest.

    A started step is conservatively uncertain after restart. This object does not
    authorize recovery or assert that the prior process has stopped.
    """

    schema_version: Literal["1"] = "1"
    run_id: RunId
    owner: CheckpointOwner
    trace: TraceIdentifiers
    manifest: WorkflowManifest
    runtime_contract: Symbol
    intent_sha256: Sha256
    arguments: PayloadRef
    steps: tuple[StepCheckpoint, ...]
    status: Literal["running", "suspended", "succeeded"] = "running"
    revision: int = Field(default=0, ge=0, strict=True)
    idempotency_key: IdempotencyKey | None = None
    resumed_from: RunId | None = None
    continued_by: RunId | None = None

    @model_validator(mode="after")
    def linear_evidence(self) -> Self:
        if [step.step_index for step in self.steps] != list(range(len(self.manifest.steps))):
            raise ValueError("checkpoint must cover every manifest step in declared order")
        remaining = False
        for step in self.steps:
            if remaining and step.state != "never_started":
                raise ValueError("only a completed prefix and one unresolved step are permitted")
            if step.state != "completed":
                remaining = True
        if (self.status == "succeeded") != (not remaining):
            raise ValueError("success requires exactly all steps completed")
        if self.run_id in {self.resumed_from, self.continued_by}:
            raise ValueError("run cannot be its own parent or continuation")
        if self.resumed_from is not None and self.resumed_from == self.continued_by:
            raise ValueError("a run cannot be continued by its own parent")
        if self.continued_by is not None and self.status != "suspended":
            raise ValueError("only a suspended run can have a continuation")
        if self.resumed_from is not None and self.idempotency_key is not None:
            raise ValueError("continuations do not consume submission keys")
        return self

    def recovery_plan(self) -> ResumePlan:
        """Metadata-only restart classification, never automatic dispatch.

        A `running` record may still belong to a live process (a caller-wait
        timeout is not abandonment), so only a `suspended` record needs input.
        """
        checked = RunCheckpoint.model_validate(self)
        steps = tuple(
            StepStateRecord(
                step_index=step.step_index,
                state="uncertain" if step.state == "started" else step.state,
                code=step.code,
            )
            for step in checked.steps
        )
        status: Literal["succeeded", "running", "needs_input"] = (
            "succeeded"
            if checked.status == "succeeded"
            else "running"
            if checked.status == "running"
            else "needs_input"
        )
        return ResumePlan(
            run_id=checked.run_id,
            workflow=checked.manifest.metadata.identity,
            status=status,
            steps=steps,
            next_step=next((s.step_index for s in steps if s.state != "completed"), None),
        )
