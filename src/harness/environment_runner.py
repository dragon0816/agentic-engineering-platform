"""Run declared validation commands in the actual IT-managed OS environment."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol

from harness.restricted_runner import RunnerError, RunnerLimits, RunResult
from integrations.process_execution import CommandRequest, ProcessStartError, run_command


class CommandRunner(Protocol):
    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path,
        run_dir: Path,
        extra_env: Mapping[str, str] | None = None,
    ) -> RunResult: ...


class EnvironmentRunner:
    def __init__(self, python: Path, limits: RunnerLimits | None = None) -> None:
        if not python.is_file():
            raise RunnerError("runner_python_missing")
        self.python = python
        self.limits = limits or RunnerLimits()

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: Path,
        run_dir: Path,
        extra_env: Mapping[str, str] | None = None,
    ) -> RunResult:
        return asyncio.run(self.run_async(args, cwd=cwd, run_dir=run_dir, extra_env=extra_env))

    async def run_async(
        self,
        args: Sequence[str],
        *,
        cwd: Path,
        run_dir: Path,
        extra_env: Mapping[str, str] | None = None,
    ) -> RunResult:
        try:
            result = await run_command(
                CommandRequest(
                    argv=(str(self.python), *args),
                    cwd=str(cwd),
                    timeout_seconds=float(self.limits.timeout_seconds),
                ),
                extra_env=extra_env,
            )
        except ProcessStartError as error:
            raise RunnerError(error.code) from None
        output = result.stdout + ("\n" if result.stdout and result.stderr else "") + result.stderr
        output = output.replace("\r\n", "\n").replace("\r", "\n")
        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "output.txt").write_text(output, encoding="utf-8")
        return RunResult(None if result.timed_out else result.exit_code, result.timed_out, output)
