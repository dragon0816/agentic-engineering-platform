"""Git worktree + restricted pytest as the harness's declared commands (C3)."""

import importlib.util
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import cast

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows execution limits")

from common.execution import TraceIdentifiers  # noqa: E402
from harness import git_worktree  # noqa: E402
from harness.contracts import (  # noqa: E402
    CandidateChange,
    CodingHarnessRequest,
    CommandOutcome,
    HarnessBudget,
    HarnessPlan,
    PlannedChange,
    WorkspaceSnapshot,
)
from harness.pytest_commands import (  # noqa: E402
    NEW_COMMAND,
    SUITE_COMMAND,
    PytestCommand,
    new_cases,
    suite_case,
)
from harness.restricted_runner import RestrictedRunner, RunnerLimits  # noqa: E402
from harness.runtime import CodingHarness, DeclaredCommands  # noqa: E402
from harness.workspace import BoundedWorkspace, WorkspaceRefused  # noqa: E402

requires_win32 = pytest.mark.skipif(
    importlib.util.find_spec("win32api") is None,
    reason="needs pywin32 (the windows extra); CI installs only dev,office",
)


TRACE = TraceIdentifiers(trace_id="coding", request_id="coding", span_id="coding")
# The suite's own pytest, read by the base interpreter the runner uses.
SITE = {"PYTHONPATH": sysconfig.get_paths()["purelib"]}

WRONG = "def double(value: int) -> int:\n    return value + 2\n"
RIGHT = "def double(value: int) -> int:\n    return value * 2\n"


def git(*args: str, cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout


def repository(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / "src" / "calc").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "src" / "calc" / "__init__.py").write_text("")
    (repo / "src" / "calc" / "ops.py").write_text(
        "def add(a: int, b: int) -> int:\n    return a + b\n"
    )
    (repo / "tests" / "test_add.py").write_text(
        "from calc.ops import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )
    (repo / "tests" / "test_double.py").write_text(
        "from calc.double import double\n\n\ndef test_double():\n    assert double(4) == 8\n\n\n"
        "def test_double_zero():\n    assert double(0) == 0\n"
    )
    (repo / "pyproject.toml").write_text('[tool.pytest.ini_options]\npythonpath = ["src"]\n')
    git("init", "-q", cwd=repo)
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "add", ".", cwd=repo)
    git("-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "start", cwd=repo)
    return repo


class Scripted:
    """Wrong first, right after one repair: the E2E-03 shape on real pytest."""

    def __init__(self) -> None:
        self.repairs: list[CommandOutcome] = []

    def plan(self, request: CodingHarnessRequest) -> HarnessPlan:
        return HarnessPlan(
            summary="add double",
            changes=(PlannedChange(path=request.artifact_path, purpose="implement"),),
            validation_commands=request.allowed_commands,
        )

    def initial_change(self, request: CodingHarnessRequest, plan: HarnessPlan) -> CandidateChange:
        return CandidateChange(path=request.artifact_path, content=WRONG)

    def repair(
        self,
        request: CodingHarnessRequest,
        plan: HarnessPlan,
        failure: CommandOutcome,
        attempt: int,
    ) -> CandidateChange:
        self.repairs.append(failure)
        return CandidateChange(path=request.artifact_path, content=RIGHT)


def harness_for(
    tmp_path: Path, author: Scripted, max_repairs: int = 1
) -> tuple[Path, git_worktree.RunWorkspace, CodingHarness, CodingHarnessRequest]:
    repo = repository(tmp_path)
    run = git_worktree.create(repo, tmp_path / "runs", "run-1")
    runner = RestrictedRunner(
        Path(getattr(sys, "_base_executable", sys.executable)), RunnerLimits(timeout_seconds=60)
    )
    commands = DeclaredCommands()
    commands.register(NEW_COMMAND, PytestCommand("new", runner, run.run_dir, SITE))
    commands.register(SUITE_COMMAND, PytestCommand("suite", runner, run.run_dir, SITE))
    artifact = "src/calc/double.py"
    request = CodingHarnessRequest(
        workspace=WorkspaceSnapshot(
            root=str(run.worktree),
            starting_revision=BoundedWorkspace(str(run.worktree), (artifact,)).revision(),
        ),
        requirement="Add double(value) returning twice the value.",
        artifact_path=artifact,
        allowed_paths=(artifact,),
        allowed_commands=(NEW_COMMAND, SUITE_COMMAND),
        cases=(*new_cases(("tests/test_double.py",)), suite_case()),
        skill_versions=("coding@1.0.0",),
        budget=HarnessBudget(max_repair_attempts=max_repairs, max_commands=6),
    )
    return repo, run, CodingHarness(commands, author), request


@requires_win32
def test_a_wrong_change_fails_real_tests_is_repaired_and_the_suite_passes(tmp_path: Path) -> None:
    author = Scripted()
    repo, run, harness, request = harness_for(tmp_path, author)
    result = harness.run(TRACE, request)
    assert result.status == "validated", result.failure
    first = result.commands[0]
    assert first.command == NEW_COMMAND and first.status == "failed"
    assert {failure.code for failure in first.failures} == {"test_failed"}
    assert all(failure.case == "new-1" for failure in first.failures)
    assert [command.command for command in result.commands[1:]] == [NEW_COMMAND, SUITE_COMMAND]
    assert author.repairs and "double" in author.repairs[0].failures[0].message
    assert len(result.changes) == 2 and not result.committed
    change = git_worktree.diff(run.worktree)
    assert "+    return value * 2" in change
    # The repository's own checkout and history are untouched.
    assert not (repo / "src" / "calc" / "double.py").exists()
    assert git("rev-list", "--count", "HEAD", cwd=repo).strip() == "1"
    git_worktree.remove(repo, run.worktree)
    assert not run.worktree.exists()


@requires_win32
def test_a_change_that_never_passes_stops_at_the_repair_budget(tmp_path: Path) -> None:
    class StillWrong(Scripted):
        def repair(self, request, plan, failure, attempt):  # type: ignore[no-untyped-def]
            return CandidateChange(
                path=request.artifact_path, content=WRONG.replace("+ 2", f"+ {attempt + 2}")
            )

    _, _, harness, request = harness_for(tmp_path, StillWrong(), max_repairs=1)
    result = harness.run(TRACE, request)
    assert result.status == "failed" and result.failure is not None
    assert result.failure.code == "repair_budget_exceeded" and result.artifact is None


@requires_win32
def test_a_repair_that_changes_nothing_is_a_typed_stop(tmp_path: Path) -> None:
    """Found on real pytest: the same file handed back made an empty patch
    and the run raised instead of answering."""

    class Stubborn(Scripted):
        def repair(self, request, plan, failure, attempt):  # type: ignore[no-untyped-def]
            return CandidateChange(path=request.artifact_path, content=WRONG)

    _, _, harness, request = harness_for(tmp_path, Stubborn(), max_repairs=2)
    result = harness.run(TRACE, request)
    assert result.status == "failed" and result.failure is not None
    assert result.failure.code == "change_made_no_difference"


@requires_win32
def test_a_missing_test_is_a_named_failure_not_a_pass(tmp_path: Path) -> None:
    author = Scripted()
    _, run, harness, request = harness_for(tmp_path, author)
    command = PytestCommand(
        "new",
        cast(PytestCommand, harness.commands._commands[NEW_COMMAND]).runner,
        run.run_dir,
        SITE,
    )
    missing = request.model_copy(
        update={"cases": (*new_cases(("tests/test_nope.py",)), suite_case())}
    )
    failures = command(BoundedWorkspace(str(run.worktree), request.allowed_paths), missing)
    assert failures and failures[0].code in {"pytest_usage_error", "no_tests_collected"}


def test_a_worktree_needs_a_git_repository(tmp_path: Path) -> None:
    (tmp_path / "plain").mkdir()
    with pytest.raises(WorkspaceRefused) as refused:
        git_worktree.create(tmp_path / "plain", tmp_path / "runs", "r")
    assert refused.value.code == "repository_not_git"
