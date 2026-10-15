"""`coding/change@1.0.0`: the bounded harness on a real repository.

Every check a person can act on comes before anything runs, as a typed
refusal: unknown repository, a file outside `writable` or a test file, a test
that does not exist, no model, a runner interpreter that cannot be
restricted, or a missing network block. Then one detached git worktree, the
model author, and restricted pytest as the only judge. A run that does not
validate is a refusal with the harness's own code; its evidence is written
next to the worktree first, so nothing the run learned is lost.
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import secrets
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from capabilities.coding_change.contracts import (
    CodingChangeResult,
    CodingChangeStepInput,
    CodingHostBinding,
    CodingRepository,
    CommandSummary,
)
from capabilities.coding_change.manifest import SKILL
from capabilities.runtime import CapabilityRefused
from common.base import Contract
from common.execution import RequestContext, TraceIdentifiers
from harness import git_worktree
from harness.contracts import CodingHarnessRequest, HarnessBudget, WorkspaceSnapshot
from harness.model_author import AuthorUnavailable, ModelChangeAuthor
from harness.network_block import outbound_rule_present
from harness.pytest_commands import (
    NEW_COMMAND,
    SUITE_COMMAND,
    PytestCommand,
    new_cases,
    suite_case,
)
from harness.restricted_runner import RestrictedRunner, RunnerError, RunnerLimits
from harness.runtime import CodingHarness, DeclaredCommands
from harness.workspace import BoundedWorkspace, WorkspaceRefused
from models.contracts import ModelClient

MAX_DIFF_CHARS = 20_000
MAX_CONTEXT_FILES = 10


def is_test_path(path: str, test_folder: str = "tests") -> bool:
    parts = PurePosixPath(path).parts
    name = parts[-1] if parts else ""
    return (
        test_folder in parts[:-1]
        or "tests" in parts[:-1]
        or name.startswith("test_")
        or name.endswith("_test.py")
        or name == "conftest.py"
    )


def _relative(path: str) -> str:
    candidate = PurePosixPath(path.strip().replace("\\", "/"))
    if (
        candidate.is_absolute()
        or ".." in candidate.parts
        or not candidate.parts
        or ":" in candidate.parts[0]
    ):
        raise CapabilityRefused("coding_path_invalid")
    return candidate.as_posix()


class CodingChangeHandler:
    def __init__(
        self,
        binding: CodingHostBinding,
        runs_root: Path,
        *,
        model: ModelClient | None,
        model_alias: str,
        local_only: bool = False,
        rule_present: Callable[[Path], bool] = outbound_rule_present,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self.binding = binding
        self.runs_root = runs_root
        self.model = model
        self.model_alias = model_alias
        self.local_only = local_only
        self.rule_present = rule_present
        self.extra_env = dict(extra_env or {})

    async def __call__(self, context: RequestContext, inputs: Contract) -> Contract:
        step = CodingChangeStepInput.model_validate(inputs)
        return await asyncio.to_thread(self.change, context.trace, step)

    def change(self, trace: TraceIdentifiers, step: CodingChangeStepInput) -> CodingChangeResult:
        request = step.request
        repository = self.binding.repository(request.repository)
        if repository is None:
            raise CapabilityRefused("coding_repository_unknown")
        root = Path(repository.path)
        file = self._writable(repository, request.file)
        tests = tuple(self._golden(repository, root, test) for test in request.tests)
        if self.model is None:
            raise CapabilityRefused("coding_model_unavailable")
        python = Path(self.binding.runner_python)
        try:
            runner = RestrictedRunner(
                python,
                RunnerLimits(
                    timeout_seconds=self.binding.timeout_seconds, memory_mb=self.binding.memory_mb
                ),
            )
        except RunnerError as error:
            raise CapabilityRefused(error.code) from None
        if self.binding.require_network_block and not self.rule_present(python):
            raise CapabilityRefused("coding_network_block_missing")
        run_id = f"{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(3)}"
        try:
            run = git_worktree.create(root, self.runs_root, run_id)
        except WorkspaceRefused as error:
            raise CapabilityRefused(f"coding_{error.code}") from None
        commands = DeclaredCommands()
        commands.register(NEW_COMMAND, PytestCommand("new", runner, run.run_dir, self.extra_env))
        commands.register(
            SUITE_COMMAND, PytestCommand("suite", runner, run.run_dir, self.extra_env)
        )
        harness_request = CodingHarnessRequest(
            workspace=WorkspaceSnapshot(
                root=str(run.worktree),
                starting_revision=BoundedWorkspace(str(run.worktree), (file,)).revision(),
            ),
            requirement=request.requirement,
            artifact_path=file,
            allowed_paths=(file,),
            allowed_commands=(NEW_COMMAND, SUITE_COMMAND),
            cases=(*new_cases(tests), suite_case(repository.test_folder)),
            skill_versions=(f"{SKILL.namespace}/{SKILL.name}@{SKILL.version}",),
            budget=HarnessBudget(
                max_repair_attempts=request.max_repairs, max_commands=2 * (request.max_repairs + 1)
            ),
        )
        author = ModelChangeAuthor(
            self.model,
            self.model_alias,
            trace,
            self._context(run.worktree, file, tests),
            local_only=self.local_only,
        )
        evidence = run.run_dir / "result.json"
        try:
            result = CodingHarness(commands, author).run(trace, harness_request)
        except AuthorUnavailable as error:
            evidence.write_text(json.dumps({"stopped": error.code}), encoding="utf-8")
            raise CapabilityRefused(error.code) from None
        diff = git_worktree.diff(run.worktree)
        evidence.write_text(
            json.dumps(
                {"result": result.model_dump(mode="json"), "diff": diff},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        if result.status != "validated":
            assert result.failure is not None
            raise CapabilityRefused(result.failure.code)
        return CodingChangeResult(
            repository=repository.name,
            worktree=str(run.worktree),
            base_revision=run.head,
            summary=result.plan.summary,
            attempts=len(result.changes),
            commands=tuple(
                CommandSummary(
                    command=item.command,
                    status=item.status,
                    failures=tuple(f.message[:500] for f in item.failures[:3]),
                )
                for item in result.commands
            ),
            diff=diff[:MAX_DIFF_CHARS] or "(no difference)",
            evidence=str(evidence),
        )

    @staticmethod
    def _writable(repository: CodingRepository, file: str) -> str:
        path = _relative(file)
        if is_test_path(path, repository.test_folder):
            raise CapabilityRefused("coding_file_is_a_test")
        if not any(fnmatch.fnmatchcase(path, pattern) for pattern in repository.writable):
            raise CapabilityRefused("coding_file_not_writable")
        return path

    @staticmethod
    def _golden(repository: CodingRepository, root: Path, test: str) -> str:
        node = test.strip().replace("\\", "/")
        path = _relative(node.split("::", 1)[0])
        if not is_test_path(path, repository.test_folder):
            raise CapabilityRefused("coding_test_not_a_test_file")
        if not (root / path).is_file():
            raise CapabilityRefused("coding_test_not_found")
        return node

    @staticmethod
    def _context(worktree: Path, file: str, tests: tuple[str, ...]) -> dict[str, str]:
        files = [file, *dict.fromkeys(test.split("::", 1)[0] for test in tests)]
        context: dict[str, str] = {}
        for path in files[:MAX_CONTEXT_FILES]:
            target = worktree / path
            context[path] = (
                target.read_text(encoding="utf-8", errors="replace")
                if target.is_file()
                else "(this file does not exist yet)"
            )
        return context
