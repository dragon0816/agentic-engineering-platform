"""Execute argv directly; OS and service permissions determine availability."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

from pydantic import Field

from common.assets import REDACTED, SECRET_PATTERN
from common.base import Contract
from integrations.process_job import WINDOWS_COMMAND_SUPERVISOR

OUTPUT_LIMIT = 65_536


class CommandRequest(Contract):
    argv: tuple[str, ...] = Field(min_length=1)
    cwd: str | None = None
    timeout_seconds: float = Field(default=20.0, gt=0, le=1800)


class CommandResult(Contract):
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False


class ProcessStartError(Exception):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


async def _drain(stream: asyncio.StreamReader | None) -> tuple[str, bool]:
    if stream is None:
        return "", False
    kept = bytearray()
    total = 0
    while chunk := await stream.read(8192):
        total += len(chunk)
        kept.extend(chunk[: max(0, OUTPUT_LIMIT - len(kept))])
    return SECRET_PATTERN.sub(REDACTED, kept.decode("utf-8", errors="replace")), total > len(kept)


async def _stop_owned(process: asyncio.subprocess.Process) -> None:
    if os.name == "nt" and process.returncode is None:
        # The owned venv launcher waits for the supervisor. Closing its job
        # kills descendants even when the requested executable already exited.
        try:
            await asyncio.to_thread(
                subprocess.run,
                [
                    os.path.join(
                        os.environ.get("SystemRoot", r"C:\Windows"), "System32", "taskkill.exe"
                    ),
                    "/PID",
                    str(process.pid),
                    "/T",
                    "/F",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            pass
    elif sys.platform != "win32":
        try:
            kill_group = os.killpg
            kill_group(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    await process.wait()


async def run_command(
    request: CommandRequest,
    *,
    extra_env: Mapping[str, str] | None = None,
) -> CommandResult:
    """The deadline covers process exit AND pipe draining; clean only owned work."""
    with tempfile.TemporaryDirectory(prefix="aep-command-") as scratch:
        status_path = Path(scratch) / "start-status.txt"
        argv_path = Path(scratch) / "argv.json"
        if os.name == "nt":
            argv_path.write_text(json.dumps(request.argv), encoding="utf-8")
        argv = (
            request.argv
            if os.name != "nt"
            else (
                sys.executable,
                "-c",
                WINDOWS_COMMAND_SUPERVISOR,
                str(status_path),
                str(argv_path),
            )
        )
        try:
            process = await asyncio.create_subprocess_exec(
                *argv,
                cwd=request.cwd,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                start_new_session=os.name != "nt",
                env={**os.environ, **extra_env} if extra_env else None,
            )
        except PermissionError:
            raise ProcessStartError("environment_denied") from None
        except FileNotFoundError:
            raise ProcessStartError("executable_not_found") from None
        except OSError:
            raise ProcessStartError("process_start_failed") from None
        stdout = asyncio.create_task(_drain(process.stdout))
        stderr = asyncio.create_task(_drain(process.stderr))
        finished = asyncio.gather(process.wait(), stdout, stderr)
        timed_out = False
        try:
            await asyncio.wait_for(asyncio.shield(finished), request.timeout_seconds)
        except TimeoutError:
            timed_out = True
            await _stop_owned(process)
            try:
                await asyncio.wait_for(asyncio.shield(finished), 5)
            except TimeoutError:
                finished.cancel()
                await asyncio.gather(finished, return_exceptions=True)
        except BaseException:
            await _stop_owned(process)
            finished.cancel()
            await asyncio.gather(finished, return_exceptions=True)
            raise
        if status_path.is_file():
            code = status_path.read_text(encoding="ascii")
            if code in {
                "environment_denied",
                "executable_not_found",
                "process_start_failed",
                "process_job_unavailable",
            }:
                raise ProcessStartError(code)
        out = ("", True) if stdout.cancelled() else stdout.result()
        err = ("", True) if stderr.cancelled() else stderr.result()
        return CommandResult(
            exit_code=process.returncode,
            stdout=out[0],
            stderr=err[0],
            timed_out=timed_out,
            stdout_truncated=out[1],
            stderr_truncated=err[1],
        )
