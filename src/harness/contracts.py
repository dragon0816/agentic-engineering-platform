"""Provider-neutral contracts for one bounded coding Harness run."""

from pathlib import PurePosixPath
from typing import Literal, Self

from pydantic import Field, JsonValue, StrictBool, field_validator, model_validator

from common.assets import reject_embedded_secrets
from common.base import Contract, Sha256, Symbol, Text
from common.execution import Failure, TraceIdentifiers


class WorkspaceSnapshot(Contract):
    """Pinned workspace state supplied by the trusted host."""

    root: Text
    starting_revision: Sha256

    @field_validator("root")
    @classmethod
    def absolute_root(cls, value: str) -> str:
        # Windows drive roots and POSIX roots are both cross-process contract values.
        normalized = value.replace("\\", "/")
        if not (
            PurePosixPath(normalized).is_absolute()
            or (len(normalized) > 2 and normalized[1:3] == ":/")
        ):
            raise ValueError("workspace root must be absolute")
        return value


class HarnessBudget(Contract):
    max_repair_attempts: int = Field(default=1, ge=0, le=3, strict=True)
    max_commands: int = Field(default=4, ge=1, le=20, strict=True)


class ValidationCase(Contract):
    name: Symbol
    kind: Literal["new", "regression"]
    input: JsonValue
    expected: JsonValue

    @model_validator(mode="after")
    def safe_evidence(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class PlannedChange(Contract):
    path: Text
    purpose: Text

    @field_validator("path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        path = PurePosixPath(value.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts or value.endswith(("/", "\\")):
            raise ValueError("change paths must be relative files without traversal")
        return path.as_posix()


class HarnessPlan(Contract):
    summary: Text
    changes: tuple[PlannedChange, ...] = Field(min_length=1)
    validation_commands: tuple[Symbol, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_scope(self) -> Self:
        paths = [change.path for change in self.changes]
        if len(paths) != len(set(paths)):
            raise ValueError("planned paths must be unique")
        if len(self.validation_commands) != len(set(self.validation_commands)):
            raise ValueError("validation commands must be unique")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class CandidateChange(Contract):
    path: Text
    content: Text

    @model_validator(mode="after")
    def safe_change(self) -> Self:
        PlannedChange(path=self.path, purpose="candidate")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class ChangeRecord(Contract):
    path: Text
    before_sha256: Sha256 | None = None
    after_sha256: Sha256
    patch: Text

    @model_validator(mode="after")
    def safe_patch(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class ValidationFailure(Contract):
    case: Symbol
    code: Symbol
    message: Text
    expected: JsonValue = None
    observed: JsonValue = None

    @model_validator(mode="after")
    def safe_failure(self) -> Self:
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class CommandOutcome(Contract):
    command: Symbol
    status: Literal["passed", "failed"]
    failures: tuple[ValidationFailure, ...] = ()

    @model_validator(mode="after")
    def status_matches_failures(self) -> Self:
        if (self.status == "passed") != (not self.failures):
            raise ValueError("command status must match its validation failures")
        return self


class HarnessEvent(Contract):
    sequence: int = Field(ge=0, strict=True)
    kind: Literal[
        "planned",
        "changed",
        "validation_failed",
        "repair_requested",
        "validated",
        "stopped",
    ]
    code: Symbol | None = None


class ArtifactRecord(Contract):
    path: Text
    sha256: Sha256


class CodingHarnessRequest(Contract):
    workspace: WorkspaceSnapshot
    requirement: Text
    artifact_path: Text
    allowed_paths: tuple[Text, ...] = Field(min_length=1)
    allowed_commands: tuple[Symbol, ...] = Field(min_length=1)
    cases: tuple[ValidationCase, ...] = Field(min_length=1)
    skill_versions: tuple[Text, ...] = Field(min_length=1)
    budget: HarnessBudget = HarnessBudget()

    @model_validator(mode="after")
    def bounded_scope(self) -> Self:
        artifact = PlannedChange(path=self.artifact_path, purpose="artifact").path
        paths = tuple(
            PlannedChange(path=path, purpose="allowed").path for path in self.allowed_paths
        )
        if artifact not in paths:
            raise ValueError("artifact path must be explicitly allowed")
        commands_unique = len(self.allowed_commands) == len(set(self.allowed_commands))
        if len(paths) != len(set(paths)) or not commands_unique:
            raise ValueError("allowed paths and commands must be unique")
        names = [case.name for case in self.cases]
        if len(names) != len(set(names)):
            raise ValueError("validation case names must be unique")
        if not any(case.kind == "new" for case in self.cases):
            raise ValueError("at least one new validation case is required")
        if not any(case.kind == "regression" for case in self.cases):
            raise ValueError("at least one regression case is required")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self


class CodingHarnessResult(Contract):
    trace: TraceIdentifiers
    workspace: WorkspaceSnapshot
    status: Literal["validated", "failed", "needs_input"]
    plan: HarnessPlan
    changes: tuple[ChangeRecord, ...]
    commands: tuple[CommandOutcome, ...]
    events: tuple[HarnessEvent, ...]
    skill_versions: tuple[Text, ...]
    artifact: ArtifactRecord | None = None
    failure: Failure | None = None
    committed: StrictBool = False
    published: StrictBool = False

    @model_validator(mode="after")
    def completion_evidence(self) -> Self:
        if self.status == "validated":
            if self.failure is not None or self.artifact is None or not self.commands:
                raise ValueError("validated runs require artifact and command evidence")
            if self.commands[-1].status != "passed":
                raise ValueError("validated runs require a final passing command")
        elif self.failure is None or self.artifact is not None:
            raise ValueError("non-validated runs require failure and forbid an artifact")
        if self.committed or self.published:
            raise ValueError("the Harness may not commit or publish")
        if [event.sequence for event in self.events] != list(range(len(self.events))):
            raise ValueError("Harness events must be contiguous and ordered")
        reject_embedded_secrets(self.model_dump(mode="json"))
        return self
