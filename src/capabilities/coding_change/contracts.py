"""Contracts of `coding/change@1.0.0` (docs/phases/CODING_ON_BRIDGE.md,
docs/phases/CODING_AT_SCALE.md)."""

from typing import Literal, Self

from pydantic import Field, StrictBool, model_validator

from common.base import Contract, Symbol, Text


class CodingChangeRequest(Contract):
    """One run's answers: which repository, what to change, in which file
    (and up to nine more it may change with it), and the existing tests that
    say when it is done."""

    repository: Symbol
    requirement: Text
    file: Text
    more_files: tuple[Text, ...] = Field(default=(), max_length=9)
    tests: tuple[Text, ...] = Field(min_length=1, max_length=20)
    max_repairs: int = Field(default=2, ge=0, le=3)


class CodingChangeStepInput(Contract):
    request: CodingChangeRequest


class CommandSummary(Contract):
    command: Symbol
    status: Literal["passed", "failed"]
    failures: tuple[Text, ...] = ()


class CodingChangeResult(Contract):
    """A validated change, left in a worktree for the owner to review.
    Never committed: `committed` exists so a reader can see that."""

    repository: Symbol
    worktree: Text
    base_revision: Text
    summary: Text
    attempts: int
    commands: tuple[CommandSummary, ...]
    diff: Text
    evidence: Text
    committed: StrictBool = False


class CodingCheck(Contract):
    """A check run after the change's own tests: `python -m <module> <args>`
    under the restricted runner in the worktree, failing on a non-zero exit.
    `{files}` in `args` becomes the files the run may change."""

    name: Symbol
    module: Symbol
    args: tuple[Text, ...] = ()


class CodingRepository(Contract):
    """One repository this Bridge may change, and the files it may write.
    `writable` holds glob patterns relative to the repository; test files are
    never writable whatever the patterns say."""

    name: Symbol
    path: Text
    writable: tuple[Text, ...] = Field(min_length=1)
    test_folder: Text = "tests"
    checks: tuple[CodingCheck, ...] = Field(default=(), max_length=5)

    @model_validator(mode="after")
    def unique_checks(self) -> Self:
        names = [check.name for check in self.checks]
        if len(names) != len(set(names)):
            raise ValueError("check names must be unique")
        return self


class CodingHostBinding(Contract):
    """Trusted host wiring for coding on the Bridge (host.json `coding`)."""

    runner_python: Text
    repositories: tuple[CodingRepository, ...] = Field(min_length=1)
    timeout_seconds: int = Field(default=120, ge=5, le=1800, strict=True)
    memory_mb: int = Field(default=1024, ge=128, le=8192, strict=True)
    # Off only for a test host: production runs refuse without the block.
    require_network_block: StrictBool = True
    # Folders a conversation task may run Python in (`coding/run-python`); a
    # workspace must lie under one of them. Empty: the capability is not installed.
    workspace_roots: tuple[Text, ...] = ()
    # Processes a `coding/run-python` script may have alive at once, itself
    # included, so it can run a command-line tool. `coding/change` stays at one.
    run_python_max_processes: int = Field(default=4, ge=1, le=16, strict=True)
    # Processes a `coding/change` test run may have alive at once. One forbids
    # child processes; more lets tests start tools, which inherit low integrity
    # and the Job but not the firewall rule (docs/phases/CODING_AT_SCALE.md).
    change_max_processes: int = Field(default=1, ge=1, le=16, strict=True)
    # The change author's turns per attempt (reads, searches, edits) and its
    # answer size per turn.
    author_max_turns: int = Field(default=30, ge=4, le=100, strict=True)
    author_max_output_tokens: int = Field(default=8_000, ge=1_000, le=64_000, strict=True)

    def repository(self, name: str) -> CodingRepository | None:
        return next((item for item in self.repositories if item.name == name), None)
