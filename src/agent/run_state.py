"""Portable, payload-free task progress and host-owned completion validation."""

import hashlib
from datetime import datetime
from typing import Literal, Protocol, Self

from pydantic import AwareDatetime, Field, model_validator

from agent.task_contract import TaskContract
from common.base import Contract, Sha256, Symbol
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


class CompletionCheckResult(Contract):
    check_id: Symbol
    status: Literal["passed", "failed"]
    code: Literal[
        "checked", "artifact_not_reported", "artifact_missing", "artifact_empty",
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
    status: TaskStatus = "pending"
    revision: int = Field(default=0, ge=0, strict=True)
    created_at: AwareDatetime
    updated_at: AwareDatetime
    observations: tuple[TaskObservation, ...] = Field(default=(), max_length=100)
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


def begin_task_run(task: TaskContract, backend_id: Symbol, *, now: datetime) -> TaskRunState:
    """Begin with a digest, not a copy of the objective or input resources."""
    return TaskRunState(
        task_id=task.task_id,
        trace=task.trace,
        actor=task.actor,
        task_sha256=task.digest,
        backend_id=backend_id,
        created_at=now,
        updated_at=now,
    )


def advance_task_run(
    state: TaskRunState,
    status: TaskStatus,
    *,
    now: datetime,
    observations: tuple[TaskObservation, ...] = (),
    artifact_refs: tuple[Symbol, ...] = (),
    validation: TaskValidationReport | None = None,
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
    return TaskRunState.model_validate(
        {
            **state.model_dump(mode="python"),
            "status": status,
            "revision": state.revision + 1,
            "updated_at": now,
            "observations": (*state.observations, *observations),
            "artifact_refs": (*state.artifact_refs, *artifact_refs),
            "validation": validation,
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
        or candidate.created_at != previous.created_at
        or candidate.revision != previous.revision + 1
        or candidate.observations[: len(previous.observations)] != previous.observations
        or candidate.artifact_refs[: len(previous.artifact_refs)] != previous.artifact_refs
    ):
        return False
    try:
        expected = advance_task_run(
            previous,
            candidate.status,
            now=candidate.updated_at,
            observations=candidate.observations[len(previous.observations) :],
            artifact_refs=candidate.artifact_refs[len(previous.artifact_refs) :],
            validation=candidate.validation,
        )
    except ValueError:
        return False
    return expected == candidate


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
                        check_id=check.check_id, status="failed", code="artifact_empty",
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
