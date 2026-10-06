"""Contracts of `coding/change@1.0.0` (docs/phases/CODING_ON_BRIDGE.md)."""

from typing import Literal

from pydantic import Field, StrictBool

from common.base import Contract, Symbol, Text


class CodingChangeRequest(Contract):
    """One run's answers: which repository, what to change, in which file,
    and the existing tests that say when it is done."""

    repository: Symbol
    requirement: Text
    file: Text
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


class CodingRepository(Contract):
    """One repository this Bridge may change, and the files it may write.
    `writable` holds glob patterns relative to the repository; test files are
    never writable whatever the patterns say."""

    name: Symbol
    path: Text
    writable: tuple[Text, ...] = Field(min_length=1)
    test_folder: Text = "tests"


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

    def repository(self, name: str) -> CodingRepository | None:
        return next((item for item in self.repositories if item.name == name), None)
