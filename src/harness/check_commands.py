"""Host-declared checks beside pytest (`docs/phases/CODING_AT_SCALE.md`).

A repository's `host.json` entry may name checks such as pylint or mypy. Each
runs as `python -m <module> <args>` under the restricted runner in the run's
worktree, so the host names the program and the model names nothing. A
non-zero exit fails the check; its scrubbed output goes back to the author.
`{files}` in the arguments becomes the files the run may change.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from common.assets import REDACTED, SECRET_PATTERN
from harness.contracts import CodingHarnessRequest, ValidationCase, ValidationFailure
from harness.restricted_runner import RestrictedRunner
from harness.workspace import BoundedWorkspace

FILES_PLACEHOLDER = "{files}"
MAX_CHECK_OUTPUT_CHARS = 4_000


def check_case(name: str) -> ValidationCase:
    return ValidationCase(name=f"check-{name}", kind="regression", input=name, expected="passed")


class ModuleCheck:
    """A `harness.runtime.ValidationCommand` running one declared module."""

    def __init__(
        self,
        name: str,
        module: str,
        args: Sequence[str],
        runner: RestrictedRunner,
        run_dir: Path,
        extra_env: Mapping[str, str] | None = None,
    ) -> None:
        self.name = name
        self.module = module
        self.args = tuple(args)
        self.runner = runner
        self.run_dir = run_dir
        self.extra_env = dict(extra_env or {})

    def __call__(
        self, workspace: BoundedWorkspace, request: CodingHarnessRequest
    ) -> tuple[ValidationFailure, ...]:
        args: list[str] = []
        for arg in self.args:
            if arg == FILES_PLACEHOLDER:
                args.extend(request.allowed_paths)
            else:
                args.append(arg)
        outcome = self.runner.run(
            ["-m", self.module, *args],
            cwd=workspace.root,
            run_dir=self.run_dir,
            extra_env=self.extra_env,
        )
        case = f"check-{self.name}"
        if outcome.timed_out:
            return (
                ValidationFailure(
                    case=case,
                    code="check_timeout",
                    message=f"{self.name} did not finish within the time limit",
                ),
            )
        if outcome.exit_code == 0:
            return ()
        output = SECRET_PATTERN.sub(REDACTED, outcome.output)[-MAX_CHECK_OUTPUT_CHARS:].strip()
        return (
            ValidationFailure(
                case=case,
                code="check_failed",
                message=f"{self.name} (exit {outcome.exit_code}):\n{output or '(no output)'}",
            ),
        )
