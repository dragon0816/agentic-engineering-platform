"""Portable, payload-free task progress and host-owned completion validation."""

import hashlib
from datetime import datetime
from typing import Literal, Protocol, Self

from pydantic import AwareDatetime, Field, model_validator

from agent.data_policy import DataClass, classification_rank
from agent.task_contract import TaskContract
from common.assets import reject_embedded_secrets
from common.base import Contract, Sha256, Symbol, Text
from common.execution import TraceIdentifiers

TaskStatus = Literal[
    "pending", "running", "awaiting_validation", "needs_input", "failed", "validated"
]
_NEXT: dict[TaskStatus, frozenset[TaskStatus]] = {
    "pending": frozenset({"running", "failed"}),
    "running": frozenset({"awaiting_validation", "needs_input", "failed"}),
    "awaiting_validation": frozenset({"validated", "failed"}),
    "needs_input": frozenset({"running", "failed"}),
    "failed": frozenset(),
    "validated": frozenset(),
}


class TaskObservation(Contract):
    """A bounded event reference. No prompt, artifact bytes or model reasoning."""

    sequence: int = Field(ge=0, strict=True)
    code: Symbol
    evidence_ref: Symbol | None = None


class TaskCompletedStep(Contract):
    """A Host-confirmed step, referenced without raw tool output."""

    step_id: Symbol
    evidence_ref: Symbol


class TaskIssue(Contract):
    """A bounded unresolved requirement or error code, never provider prose."""

    code: Symbol
    evidence_ref: Symbol | None = None


class BackendUse(Contract):
    """Selected backend at one authorized transition; no transferred payload."""

    backend_id: Symbol
    started_revision: int = Field(ge=0, strict=True)
    classification: DataClass
    approval_ref: Text | None = None

    @model_validator(mode="after")
    def reference_is_not_a_credential(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class TaskBackendResult(Contract):
    """A candidate outcome. Completion still requires host validation."""

    task_id: Symbol
    trace: TraceIdentifiers
    backend_id: Symbol
    status: Literal["completed", "needs_input", "failed"]
    observations: tuple[TaskObservation, ...] = Field(default=(), max_length=100)
    completed_steps: tuple[TaskCompletedStep, ...] = Field(default=(), max_length=100)
    artifact_refs: tuple[Symbol, ...] = Field(default=(), max_length=50)
    failure_code: Symbol | None = None

    @model_validator(mode="after")
    def result_shape(self) -> Self:
        if (self.status == "completed") != (self.failure_code is None):
            raise ValueError("non-completed backend result requires a failure code")
        if len(self.artifact_refs) != len(set(self.artifact_refs)):
            raise ValueError("backend artifact references must be unique")
        return self


class CompletionCheckResult(Contract):
    check_id: Symbol
    status: Literal["passed", "failed"]
    code: Literal[
        "checked",
        "artifact_not_reported",
        "artifact_missing",
        "artifact_empty",
        "artifact_digest_mismatch",
    ]
    observed_sha256: Sha256 | None = None
    size_bytes: int | None = Field(default=None, ge=0, strict=True)

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        if (self.status == "passed") != (self.code == "checked"):
            raise ValueError("a passing check must have checked its artifact")
        return self


class TaskValidationReport(Contract):
    task_id: Symbol
    task_sha256: Sha256
    run_revision: int = Field(ge=0, strict=True)
    status: Literal["passed", "failed"]
    checks: tuple[CompletionCheckResult, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def status_matches_checks(self) -> Self:
        if (self.status == "passed") != all(item.status == "passed" for item in self.checks):
            raise ValueError("validation status must match every check")
        if len(self.checks) != len({item.check_id for item in self.checks}):
            raise ValueError("validation check IDs must be unique")
        return self


class TaskRunState(Contract):
    """Resume metadata only. The caller must resupply the exact TaskContract."""

    task_id: Symbol
    trace: TraceIdentifiers
    actor: Symbol
    task_sha256: Sha256
    backend_id: Symbol
    effective_classification: DataClass
    backend_history: tuple[BackendUse, ...] = Field(min_length=1, max_length=8)
    status: TaskStatus = "pending"
    revision: int = Field(default=0, ge=0, strict=True)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    observations: tuple[TaskObservation, ...] = Field(default=(), max_length=100)
    completed_steps: tuple[TaskCompletedStep, ...] = Field(default=(), max_length=100)
    unresolved_requirements: tuple[TaskIssue, ...] = Field(default=(), max_length=30)
    errors: tuple[TaskIssue, ...] = Field(default=(), max_length=30)
    artifact_refs: tuple[Symbol, ...] = Field(default=(), max_length=50)
    validation: TaskValidationReport | None = None

    @model_validator(mode="after")
    def consistent_evidence(self) -> Self:
        if self.updated_at < self.created_at:
            raise ValueError("task update predates creation")
        if [item.sequence for item in self.observations] != list(range(len(self.observations))):
            raise ValueError("task observations must be contiguous")
        if len(self.artifact_refs) != len(set(self.artifact_refs)):
            raise ValueError("task artifact references must be unique")
        if len({item.step_id for item in self.completed_steps}) != len(self.completed_steps):
            raise ValueError("completed task steps must be unique")
        if self.backend_history[0].started_revision != 0 or (
            self.backend_history[-1].backend_id != self.backend_id
        ):
            raise ValueError("task backend history must begin at revision zero and end at current")
        if [item.started_revision for item in self.backend_history] != sorted(
            {item.started_revision for item in self.backend_history}
        ):
            raise ValueError("backend history revisions must be unique and ordered")
        if self.backend_history[-1].started_revision > self.revision:
            raise ValueError("backend transition cannot follow the current revision")
        if classification_rank(self.effective_classification) < classification_rank(
            self.backend_history[-1].classification
        ):
            raise ValueError("run classification cannot be lower than backend selection")
        if self.status == "validated" and (
            self.validation is None or self.validation.status != "passed"
        ):
            raise ValueError("validated task requires passing validation")
        if self.validation is not None:
            if self.status not in {"validated", "failed"}:
                raise ValueError("validation requires a terminal task state")
            if self.validation.status == "passed" and self.status != "validated":
                raise ValueError("passing validation requires validated task state")
            if (
                self.validation.task_id != self.task_id
                or self.validation.task_sha256 != self.task_sha256
                or self.validation.run_revision != self.revision - 1
            ):
                raise ValueError("validation does not match task revision")
        return self


def begin_task_run(
    task: TaskContract,
    backend_id: Symbol,
    *,
    now: datetime,
    effective_classification: DataClass | None = None,
    approval_ref: Text | None = None,
) -> TaskRunState:
    """Begin with a digest, not a copy of the objective or input resources."""
    classification = (
        task.declared_classification
        if effective_classification is None
        else effective_classification
    )
    if classification_rank(classification) < classification_rank(task.declared_classification):
        raise ValueError("initial task classification cannot be lowered")
    return TaskRunState(
        task_id=task.task_id,
        trace=task.trace,
        actor=task.actor,
        task_sha256=task.digest,
        backend_id=backend_id,
        effective_classification=classification,
        backend_history=(
            BackendUse(
                backend_id=backend_id,
                started_revision=0,
                classification=classification,
                approval_ref=approval_ref,
            ),
        ),
        created_at=now,
        updated_at=now,
    )


def advance_task_run(
    state: TaskRunState,
    status: TaskStatus,
    *,
    now: datetime,
    observations: tuple[TaskObservation, ...] = (),
    completed_steps: tuple[TaskCompletedStep, ...] = (),
    unresolved_requirements: tuple[TaskIssue, ...] = (),
    errors: tuple[TaskIssue, ...] = (),
    artifact_refs: tuple[Symbol, ...] = (),
    validation: TaskValidationReport | None = None,
    effective_classification: DataClass | None = None,
) -> TaskRunState:
    """One append-only transition. A completed run cannot be reopened."""
    if status not in _NEXT[state.status]:
        raise ValueError("invalid task state transition")
    if now < state.updated_at:
        raise ValueError("task update is stale")
    if [item.sequence for item in observations] != list(
        range(len(state.observations), len(state.observations) + len(observations))
    ):
        raise ValueError("task observations must append in order")
    if len(artifact_refs) != len(set(artifact_refs)) or set(artifact_refs).intersection(
        state.artifact_refs
    ):
        raise ValueError("task artifact references must append uniquely")
    existing_steps = {item.step_id for item in state.completed_steps}
    new_steps = [item.step_id for item in completed_steps]
    if len(new_steps) != len(set(new_steps)) or existing_steps.intersection(new_steps):
        raise ValueError("completed task steps must append uniquely")
    if validation is not None and state.status != "awaiting_validation":
        raise ValueError("validation follows only an awaiting task")
    if status == "validated" and (validation is None or validation.status != "passed"):
        raise ValueError("validated task requires passing validation")
    if validation is not None and (
        validation.task_id != state.task_id
        or validation.task_sha256 != state.task_sha256
        or validation.run_revision != state.revision
    ):
        raise ValueError("validation does not match task revision")
    classification = (
        state.effective_classification
        if effective_classification is None
        else effective_classification
    )
    if classification_rank(classification) < classification_rank(state.effective_classification):
        raise ValueError("task classification cannot be lowered")
    if classification != state.effective_classification and not any(
        observation.code == "classification_raised" and observation.evidence_ref is not None
        for observation in observations
    ):
        raise ValueError("classification increase requires an evidence reference")
    return TaskRunState.model_validate(
        {
            **state.model_dump(mode="python"),
            "status": status,
            "revision": state.revision + 1,
            "updated_at": now,
            "observations": (*state.observations, *observations),
            "completed_steps": (*state.completed_steps, *completed_steps),
            "unresolved_requirements": (
                *state.unresolved_requirements,
                *unresolved_requirements,
            ),
            "errors": (*state.errors, *errors),
            "artifact_refs": (*state.artifact_refs, *artifact_refs),
            "validation": validation,
            "effective_classification": classification,
        }
    )


def task_run_follows(previous: TaskRunState, candidate: TaskRunState) -> bool:
    """Check a persisted update against the same transition rules as the host."""
    if (
        candidate.task_id != previous.task_id
        or candidate.trace != previous.trace
        or candidate.actor != previous.actor
        or candidate.task_sha256 != previous.task_sha256
        or candidate.backend_id != previous.backend_id
        or candidate.backend_history != previous.backend_history
        or candidate.created_at != previous.created_at
        or candidate.revision != previous.revision + 1
        or candidate.observations[: len(previous.observations)] != previous.observations
        or candidate.completed_steps[: len(previous.completed_steps)] != previous.completed_steps
        or candidate.unresolved_requirements[: len(previous.unresolved_requirements)]
        != previous.unresolved_requirements
        or candidate.errors[: len(previous.errors)] != previous.errors
        or candidate.artifact_refs[: len(previous.artifact_refs)] != previous.artifact_refs
    ):
        return False
    try:
        expected = advance_task_run(
            previous,
            candidate.status,
            now=candidate.updated_at,
            observations=candidate.observations[len(previous.observations) :],
            completed_steps=candidate.completed_steps[len(previous.completed_steps) :],
            unresolved_requirements=candidate.unresolved_requirements[
                len(previous.unresolved_requirements) :
            ],
            errors=candidate.errors[len(previous.errors) :],
            artifact_refs=candidate.artifact_refs[len(previous.artifact_refs) :],
            validation=candidate.validation,
            effective_classification=candidate.effective_classification,
        )
    except ValueError:
        return False
    return expected == candidate


def apply_backend_result(
    state: TaskRunState, result: TaskBackendResult, *, now: datetime
) -> TaskRunState:
    """Normalize a backend claim into pending validation or a stopped run."""
    if state.status != "running":
        raise ValueError("backend result requires a running task")
    if (
        result.task_id != state.task_id
        or result.trace != state.trace
        or result.backend_id != state.backend_id
    ):
        raise ValueError("backend result does not match selected task and backend")
    if result.status == "completed":
        target: TaskStatus = "awaiting_validation"
    elif result.status == "needs_input":
        target = "needs_input"
    else:
        target = "failed"
    return advance_task_run(
        state,
        target,
        now=now,
        observations=result.observations,
        completed_steps=result.completed_steps,
        unresolved_requirements=(
            (TaskIssue(code=result.failure_code),)
            if result.status == "needs_input" and result.failure_code is not None
            else ()
        ),
        errors=(
            (TaskIssue(code=result.failure_code),)
            if result.status == "failed" and result.failure_code is not None
            else ()
        ),
        artifact_refs=result.artifact_refs,
    )


class ArtifactReader(Protocol):
    """Trusted host-side artifact resolver; native/model backends never supply it."""

    def read(self, artifact_ref: str) -> bytes | None: ...


class CompletionValidator:
    """Check actual artifact bytes, independent of the selected backend."""

    def __init__(self, artifacts: ArtifactReader) -> None:
        self._artifacts = artifacts

    def validate(self, task: TaskContract, state: TaskRunState) -> TaskValidationReport:
        if (
            task.task_id != state.task_id
            or task.trace != state.trace
            or task.actor != state.actor
            or task.digest != state.task_sha256
        ):
            raise ValueError("task digest or identity does not match the run")
        if state.status != "awaiting_validation":
            raise ValueError("task is not awaiting validation")
        outputs = {output.output_id: output for output in task.expected_outputs}
        inspected: dict[str, bytes | None] = {}
        results: list[CompletionCheckResult] = []
        for check in task.checks:
            artifact_ref = outputs[check.output_id].artifact_ref
            if artifact_ref not in state.artifact_refs:
                results.append(
                    CompletionCheckResult(
                        check_id=check.check_id, status="failed", code="artifact_not_reported"
                    )
                )
                continue
            if artifact_ref not in inspected:
                inspected[artifact_ref] = self._artifacts.read(artifact_ref)
            content = inspected[artifact_ref]
            if content is None:
                results.append(
                    CompletionCheckResult(
                        check_id=check.check_id, status="failed", code="artifact_missing"
                    )
                )
                continue
            if not content:
                results.append(
                    CompletionCheckResult(
                        check_id=check.check_id,
                        status="failed",
                        code="artifact_empty",
                        size_bytes=0,
                    )
                )
                continue
            digest = hashlib.sha256(content).hexdigest()
            matches = check.kind != "sha256" or digest == check.expected_sha256
            results.append(
                CompletionCheckResult(
                    check_id=check.check_id,
                    status="passed" if matches else "failed",
                    code="checked" if matches else "artifact_digest_mismatch",
                    observed_sha256=digest,
                    size_bytes=len(content),
                )
            )
        return TaskValidationReport(
            task_id=task.task_id,
            task_sha256=task.digest,
            run_revision=state.revision,
            status="passed" if all(item.status == "passed" for item in results) else "failed",
            checks=tuple(results),
        )
