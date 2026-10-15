"""Bounded plan/change/validate/repair loop with injected commands only."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable
from difflib import unified_diff
from typing import Protocol

import telemetry.recorder as telemetry
from agent.harness_plan import build_plan
from agent.harness_run import HarnessCheckResult
from agent.harness_runner import HarnessActionFailure, run_harness
from agent.skills import SkillHarnessGuidance
from common.assets import AssetIdentity
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
        """One coding change on the shared Harness (unification U2, owner
        2026-10-09): plan is collect, change is execute, the declared commands
        are the Host check, and a repair retries from execute. The result, its
        events and its failure codes are what this harness always returned."""
        checked = CodingHarnessRequest.model_validate(request)
        with telemetry.run(
            "coding_change",
            trace_id=trace.trace_id,
            attributes={"skill_id": checked.skill_versions[0]},
        ):
            result = self._run(trace, checked)
            telemetry.set_run(
                outcome=result.status,
                status="succeeded" if result.status == "validated" else "failed",
                failure_code=None if result.failure is None else result.failure.code,
            )
            return result

    def _run(self, trace: TraceIdentifiers, checked: CodingHarnessRequest) -> CodingHarnessResult:
        actions = CodingActions(self, checked)
        plan = build_plan(
            task_id=f"coding-{checked.workspace.starting_revision[:12]}",
            task_sha256=hashlib.sha256(checked.model_dump_json().encode()).hexdigest(),
            domain="coding",
            skill=_skill_identity(checked.skill_versions[0]),
            # The Host's budget decides; the guidance only says "repair".
            guidance=SkillHarnessGuidance(domains=("coding",), fallback="retry", max_retries=3),
            host_checks=(DECLARED_CHECK,),
            max_retries=checked.budget.max_repair_attempts,
            retry_from="execute",
            exhausted_code="repair_budget_exceeded",
        )
        run = run_harness(plan, actions)
        if actions.plan is None:  # the author's plan never arrived
            raise RuntimeError("coding harness ended before a plan")
        if run.phase == "validated":
            try:
                artifact = actions.workspace_or_refuse().read(checked.artifact_path)
                if artifact is None:
                    raise WorkspaceRefused("artifact_missing")
            except WorkspaceRefused as error:
                return actions.stopped(trace, error.code)
            return CodingHarnessResult(
                trace=trace,
                workspace=checked.workspace,
                status="validated",
                plan=actions.plan,
                changes=tuple(actions.changes),
                commands=tuple(actions.outcomes),
                events=tuple(actions.events),
                skill_versions=checked.skill_versions,
                artifact=ArtifactRecord(path=checked.artifact_path, sha256=sha256_bytes(artifact)),
            )
        return actions.stopped(trace, run.failure_code or "harness_failed")

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
        if before == encoded:
            # A real author can hand back the file it was asked to repair;
            # that is a stop, not an empty change record.
            raise WorkspaceRefused("change_made_no_difference")
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


DECLARED_CHECK = "declared_commands"


def _skill_identity(text: str) -> AssetIdentity:
    """`namespace/name@1.2.3` as an identity; anything else is the harness itself."""
    match = re.fullmatch(r"([a-z0-9][a-z0-9-]*)/([a-z0-9][a-z0-9-]*)@(\d+\.\d+\.\d+)", text)
    if match is None:
        return AssetIdentity(namespace="engineering", name="coding-harness", version="1.0.0")
    return AssetIdentity(namespace=match[1], name=match[2], version=match[3])


class CodingActions:
    """The coding domain's `HarnessActions`. The author proposes; the Host's
    declared commands decide; a refusal at a governed boundary stops the run."""

    def __init__(self, harness: CodingHarness, request: CodingHarnessRequest) -> None:
        self.harness = harness
        self.request = request
        self.plan: HarnessPlan | None = None
        self.workspace: BoundedWorkspace | None = None
        self.candidate: CandidateChange | None = None
        self.failure: CommandOutcome | None = None
        self.attempt = 0
        self.events: list[HarnessEvent] = []
        self.outcomes: list[CommandOutcome] = []
        self.changes: list[ChangeRecord] = []

    def workspace_or_refuse(self) -> BoundedWorkspace:
        if self.workspace is None:
            raise WorkspaceRefused("workspace_unavailable")
        return self.workspace

    def collect_context(self) -> str:
        request = self.request
        self.plan = self.harness.author.plan(request)
        self.events.append(HarnessEvent(sequence=0, kind="planned"))
        try:
            self.workspace = BoundedWorkspace(request.workspace.root, request.allowed_paths)
            if self.workspace.revision() != request.workspace.starting_revision:
                raise WorkspaceRefused("workspace_revision_changed")
            self.harness._validate_plan(request, self.plan)
        except WorkspaceRefused as error:
            raise HarnessActionFailure(error.code) from None
        self.candidate = self.harness.author.initial_change(request, self.plan)
        return "plan_ready"

    def execute(self) -> str:
        assert self.plan is not None
        if self.failure is not None:  # a retry: ask for the repair first
            self.events.append(HarnessEvent(sequence=len(self.events), kind="repair_requested"))
            self.attempt += 1
            self.candidate = self.harness.author.repair(
                self.request, self.plan, self.failure, self.attempt
            )
            self.failure = None
        assert self.candidate is not None
        try:
            self.harness._apply(
                self.workspace_or_refuse(), self.request, self.candidate, self.changes
            )
        except WorkspaceRefused as error:
            raise HarnessActionFailure(error.code) from None
        self.events.append(HarnessEvent(sequence=len(self.events), kind="changed"))
        return f"change-{self.attempt}"

    def validate(self) -> tuple[HarnessCheckResult, ...]:
        assert self.plan is not None
        try:
            outcome = self.harness._validate(
                self.workspace_or_refuse(), self.request, self.plan, self.outcomes
            )
        except WorkspaceRefused as error:
            raise HarnessActionFailure(error.code) from None
        passed = outcome.status == "passed"
        self.events.append(
            HarnessEvent(
                sequence=len(self.events),
                kind="validated" if passed else "validation_failed",
                code=None if passed else "validation_failed",
            )
        )
        if not passed:
            self.failure = outcome
        return (
            HarnessCheckResult(
                check_id=DECLARED_CHECK,
                status="passed" if passed else "failed",
                evidence_ref=f"commands-{len(self.outcomes)}",
            ),
        )

    def stopped(self, trace: TraceIdentifiers, code: str) -> CodingHarnessResult:
        assert self.plan is not None
        return self.harness._stopped(
            trace, self.request, self.plan, self.events, code, self.outcomes, self.changes
        )
