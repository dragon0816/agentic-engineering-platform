"""Durable run journal: the write-ahead ordering that makes restart recovery honest.

`RunJournal` joins a `CheckpointStore` and a `PayloadStore` into the sequence
`docs/WORKFLOW_CHECKPOINTS.md` specifies: acknowledge `started` durably *before*
a step is dispatched, and acknowledge `completed` only *after* the validated
result payload is committed. A failed or ambiguous acknowledgment forbids the
next action, so a restart never claims a step ran that did not, or that a step
that may have run did not.

Suspension is manual by design (approved scope): nothing here probes processes,
takes leases or decides that a previous run is dead. A human confirms that, and
the confirmation is recorded.
"""

import hashlib
import json
from dataclasses import dataclass
from typing import Literal, Self

from pydantic import JsonValue, model_validator

from common.assets import AssetIdentity, WorkflowManifest
from common.base import Contract, Symbol, Text
from common.checkpoints import CheckpointOwner, PayloadRef, RunCheckpoint, StepCheckpoint
from common.execution import IdempotencyKey, RequestContext, ResumePlan, RunId
from workflow.checkpoints import CheckpointStore, CheckpointStoreError
from workflow.payloads import PayloadStore

RUNTIME_CONTRACT = "workflow.v1"
ARGUMENTS_CONTRACT = "workflow.run-arguments.v1"
STEP_RESULT_CONTRACT = "workflow.step-result.v1"


class SuspensionConfirmation(Contract):
    """A person stating that the process which owned a run is gone.

    `process_confirmed_stopped` must be exactly `True`: the platform cannot
    check this, so it is recorded as a human's explicit claim, never a default.
    """

    operator: Symbol
    process_confirmed_stopped: Literal[True]
    note: Text | None = None


class JournalEntry(Contract):
    """What a caller may see about a journalled run without reading payloads."""

    run_id: RunId
    plan: ResumePlan
    suspended_by: Symbol | None = None

    @model_validator(mode="after")
    def suspension_matches(self) -> Self:
        if self.suspended_by is not None and self.plan.status == "running":
            raise ValueError("a suspended run is not running")
        return self


@dataclass
class JournalState:
    """One run's place in the journal; the engine holds it for the run's life."""

    checkpoint: RunCheckpoint

    @property
    def revision(self) -> int:
        return self.checkpoint.revision


def intent_signature(
    workflow: AssetIdentity, context: RequestContext, arguments: dict[str, JsonValue]
) -> str:
    """Exact workflow, arguments and every non-trace context field, order-insensitive."""
    intent = {
        "workflow": workflow.model_dump(mode="json"),
        "context": context.model_dump(mode="json", exclude={"trace"}),
        "arguments": arguments,
    }
    return hashlib.sha256(
        json.dumps(
            intent, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(",", ":")
        ).encode()
    ).hexdigest()


class RunJournal:
    """Trusted coordinator seam. Every method either commits or raises a closed code."""

    def __init__(
        self,
        checkpoints: CheckpointStore,
        payloads: PayloadStore,
        *,
        runtime_contract: str = RUNTIME_CONTRACT,
    ) -> None:
        self.checkpoints = checkpoints
        self.payloads = payloads
        self.runtime_contract = runtime_contract

    @staticmethod
    def owner_of(context: RequestContext) -> CheckpointOwner:
        return CheckpointOwner(actor=context.actor, namespace=context.namespace)

    def begin(
        self,
        run_id: RunId,
        context: RequestContext,
        manifest: WorkflowManifest,
        arguments: dict[str, JsonValue],
        *,
        idempotency_key: IdempotencyKey | None = None,
    ) -> JournalState:
        """Commit the arguments and the run record before anything executes."""
        owner = self.owner_of(context)
        reference = self.payloads.put(owner, ARGUMENTS_CONTRACT, arguments)
        checkpoint = RunCheckpoint(
            run_id=run_id,
            owner=owner,
            trace=context.trace,
            manifest=manifest,
            runtime_contract=self.runtime_contract,
            intent_sha256=intent_signature(manifest.metadata.identity, context, arguments),
            arguments=reference,
            steps=tuple(StepCheckpoint(step_index=index) for index in range(len(manifest.steps))),
            idempotency_key=idempotency_key,
        )
        return JournalState(self.checkpoints.create(checkpoint))

    def step_started(self, state: JournalState, index: int) -> None:
        """Must be acknowledged before the step is dispatched."""
        state.checkpoint = self._write(
            state, index, StepCheckpoint(step_index=index, state="started")
        )

    def step_completed(
        self, state: JournalState, index: int, context: RequestContext, data: JsonValue
    ) -> None:
        """The payload is committed first; only then is the step recorded complete."""
        reference = self.payloads.put(self.owner_of(context), STEP_RESULT_CONTRACT, data)
        state.checkpoint = self._write(
            state, index, StepCheckpoint(step_index=index, state="completed", result=reference)
        )

    def _write(self, state: JournalState, index: int, step: StepCheckpoint) -> RunCheckpoint:
        """A run whose every step is completed *is* succeeded, so the last step's
        completion and the terminal marker are one write, never two."""
        steps = list(state.checkpoint.steps)
        steps[index] = step
        done = all(item.state == "completed" for item in steps)
        updated = state.checkpoint.model_copy(
            update={"steps": tuple(steps), "status": "succeeded" if done else "running"}
        )
        return self.checkpoints.replace(updated, expected_revision=state.checkpoint.revision)

    def read(self, context: RequestContext, run_id: RunId) -> JournalEntry | None:
        """Metadata-only restart evidence for the run's owner; never dispatch."""
        checkpoint = self.checkpoints.get(self.owner_of(context), run_id)
        if checkpoint is None:
            return None
        return JournalEntry(
            run_id=checkpoint.run_id,
            plan=checkpoint.recovery_plan(),
            suspended_by=None if checkpoint.status != "suspended" else "operator",
        )

    def suspend(
        self, context: RequestContext, run_id: RunId, confirmation: SuspensionConfirmation
    ) -> JournalEntry:
        """Record a human's confirmation that the owning process is gone.

        The platform never infers this. A run that is still executing in this
        process is refused by the engine before this is reached.
        """
        checked = SuspensionConfirmation.model_validate(confirmation)
        owner = self.owner_of(context)
        checkpoint = self.checkpoints.get(owner, run_id)
        if checkpoint is None:
            raise CheckpointStoreError("missing")
        if checkpoint.status != "running":
            raise CheckpointStoreError("invalid_transition")
        updated = self.checkpoints.replace(
            checkpoint.model_copy(update={"status": "suspended"}),
            expected_revision=checkpoint.revision,
        )
        return JournalEntry(
            run_id=updated.run_id,
            plan=updated.recovery_plan(),
            suspended_by=checked.operator,
        )

    def continuation(
        self, state_run_id: RunId, context: RequestContext, parent: RunCheckpoint
    ) -> JournalState:
        """Reserve the parent's single continuation and create the child record."""
        child = parent.model_copy(
            update={
                "run_id": state_run_id,
                "trace": context.trace,
                "revision": 0,
                "status": "running",
                "resumed_from": parent.run_id,
                "continued_by": None,
                "idempotency_key": None,
            }
        )
        return JournalState(
            self.checkpoints.continue_run(child, expected_parent_revision=parent.revision)
        )

    def restore(
        self, context: RequestContext, checkpoint: RunCheckpoint
    ) -> tuple[dict[str, JsonValue], list[JsonValue]]:
        """Arguments and completed step data, each verified against its reference."""
        owner = self.owner_of(context)
        arguments = self.payloads.get(owner, checkpoint.arguments)
        if not isinstance(arguments, dict):
            raise CheckpointStoreError("unavailable")
        completed: list[JsonValue] = []
        for step in checkpoint.steps:
            if step.state != "completed":
                break
            reference: PayloadRef | None = step.result
            if reference is None:  # pragma: no cover - the contract forbids it
                raise CheckpointStoreError("unavailable")
            completed.append(self.payloads.get(owner, reference))
        return arguments, completed
