"""Bounded plan/change/validate/repair loop with injected commands only."""

from __future__ import annotations

from collections.abc import Callable
from difflib import unified_diff
from typing import Protocol

from common.execution import Failure, TraceIdentifiers
from harness.contracts import (
    ArtifactRecord,
    CandidateChange,
    ChangeRecord,
    CodingHarnessRequest,
    CodingHarnessResult,
    CommandOutcome,
    HarnessEvent,
    HarnessPlan,
    ValidationFailure,
)
from harness.workspace import BoundedWorkspace, WorkspaceRefused, sha256_bytes

ValidationCommand = Callable[
    [BoundedWorkspace, CodingHarnessRequest], tuple[ValidationFailure, ...]
]


class ChangeAuthor(Protocol):
    def plan(self, request: CodingHarnessRequest) -> HarnessPlan: ...

    def initial_change(
        self, request: CodingHarnessRequest, plan: HarnessPlan
    ) -> CandidateChange: ...

    def repair(
        self,
        request: CodingHarnessRequest,
        plan: HarnessPlan,
        failure: CommandOutcome,
        attempt: int,
    ) -> CandidateChange: ...


class DeclaredCommands:
    def __init__(self) -> None:
        self._commands: dict[str, ValidationCommand] = {}

    def register(self, name: str, command: ValidationCommand) -> None:
        if name in self._commands:
            raise ValueError("command already registered")
        self._commands[name] = command

    def run(
        self, name: str, workspace: BoundedWorkspace, request: CodingHarnessRequest
    ) -> CommandOutcome:
        if name not in request.allowed_commands:
            raise WorkspaceRefused("command_not_allowed")
        command = self._commands.get(name)
        if command is None:
            raise WorkspaceRefused("command_not_installed")
        failures = command(workspace, request)
        return CommandOutcome(
            command=name, status="failed" if failures else "passed", failures=failures
        )


class CodingHarness:
    def __init__(self, commands: DeclaredCommands, author: ChangeAuthor) -> None:
        self.commands = commands
        self.author = author

    def run(self, trace: TraceIdentifiers, request: CodingHarnessRequest) -> CodingHarnessResult:
        checked = CodingHarnessRequest.model_validate(request)
        plan = self.author.plan(checked)
        events = [HarnessEvent(sequence=0, kind="planned")]
        outcomes: list[CommandOutcome] = []
        changes: list[ChangeRecord] = []
        try:
            workspace = BoundedWorkspace(checked.workspace.root, checked.allowed_paths)
            if workspace.revision() != checked.workspace.starting_revision:
                return self._stopped(trace, checked, plan, events, "workspace_revision_changed")
            self._validate_plan(checked, plan)
            candidate = self.author.initial_change(checked, plan)
            for attempt in range(checked.budget.max_repair_attempts + 1):
                self._apply(workspace, checked, candidate, changes)
                events.append(HarnessEvent(sequence=len(events), kind="changed"))
                outcome = self._validate(workspace, checked, plan, outcomes)
                events.append(
                    HarnessEvent(
                        sequence=len(events),
                        kind="validated" if outcome.status == "passed" else "validation_failed",
                        code=None if outcome.status == "passed" else "validation_failed",
                    )
                )
                if outcome.status == "passed":
                    artifact = workspace.read(checked.artifact_path)
                    if artifact is None:
                        raise WorkspaceRefused("artifact_missing")
                    return CodingHarnessResult(
                        trace=trace,
                        workspace=checked.workspace,
                        status="validated",
                        plan=plan,
                        changes=tuple(changes),
                        commands=tuple(outcomes),
                        events=tuple(events),
                        skill_versions=checked.skill_versions,
                        artifact=ArtifactRecord(
                            path=checked.artifact_path, sha256=sha256_bytes(artifact)
                        ),
                    )
                if attempt >= checked.budget.max_repair_attempts:
                    return self._stopped(
                        trace,
                        checked,
                        plan,
                        events,
                        "repair_budget_exceeded",
                        outcomes,
                        changes,
                    )
                events.append(HarnessEvent(sequence=len(events), kind="repair_requested"))
                candidate = self.author.repair(checked, plan, outcome, attempt + 1)
        except WorkspaceRefused as error:
            return self._stopped(trace, checked, plan, events, error.code, outcomes, changes)
        return self._stopped(trace, checked, plan, events, "harness_failed", outcomes, changes)

    @staticmethod
    def _validate_plan(request: CodingHarnessRequest, plan: HarnessPlan) -> None:
        if any(change.path not in request.allowed_paths for change in plan.changes):
            raise WorkspaceRefused("plan_path_not_allowed")
        if any(command not in request.allowed_commands for command in plan.validation_commands):
            raise WorkspaceRefused("plan_command_not_allowed")

    @staticmethod
    def _apply(
        workspace: BoundedWorkspace,
        request: CodingHarnessRequest,
        candidate: CandidateChange,
        changes: list[ChangeRecord],
    ) -> None:
        if candidate.path not in request.allowed_paths:
            raise WorkspaceRefused("change_path_not_allowed")
        before = workspace.read(candidate.path)
        encoded = candidate.content.encode("utf-8")
        workspace.write(candidate.path, candidate.content)
        before_text = before.decode("utf-8") if before is not None else ""
        patch = "".join(
            unified_diff(
                before_text.splitlines(keepends=True),
                candidate.content.splitlines(keepends=True),
                fromfile=f"a/{candidate.path}",
                tofile=f"b/{candidate.path}",
            )
        )
        changes.append(
            ChangeRecord(
                path=candidate.path,
                before_sha256=sha256_bytes(before) if before is not None else None,
                after_sha256=sha256_bytes(encoded),
                patch=patch,
            )
        )

    def _validate(
        self,
        workspace: BoundedWorkspace,
        request: CodingHarnessRequest,
        plan: HarnessPlan,
        outcomes: list[CommandOutcome],
    ) -> CommandOutcome:
        last: CommandOutcome | None = None
        for name in plan.validation_commands:
            if len(outcomes) >= request.budget.max_commands:
                raise WorkspaceRefused("command_budget_exceeded")
            last = self.commands.run(name, workspace, request)
            outcomes.append(last)
            if last.status == "failed":
                return last
        if last is None:
            raise WorkspaceRefused("validation_missing")
        return last

    @staticmethod
    def _stopped(
        trace: TraceIdentifiers,
        request: CodingHarnessRequest,
        plan: HarnessPlan,
        events: list[HarnessEvent],
        code: str,
        outcomes: list[CommandOutcome] | None = None,
        changes: list[ChangeRecord] | None = None,
    ) -> CodingHarnessResult:
        events.append(HarnessEvent(sequence=len(events), kind="stopped", code=code))
        needs_input = code.endswith("not_allowed") or code.endswith("changed")
        return CodingHarnessResult(
            trace=trace,
            workspace=request.workspace,
            status="needs_input" if needs_input else "failed",
            plan=plan,
            changes=tuple(changes or ()),
            commands=tuple(outcomes or ()),
            events=tuple(events),
            skill_versions=request.skill_versions,
            failure=Failure(code=code, message="Coding Harness stopped at a governed boundary"),
        )
