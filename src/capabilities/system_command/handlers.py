"""Execute argv directly; OS and service permissions determine availability."""

from __future__ import annotations

import asyncio
import os
import subprocess

from pydantic import Field

from capabilities.contracts import CapabilitySpec
from capabilities.runtime import CapabilityExecutionFailed, CapabilityRefused, InstalledCapabilities
from common.assets import REDACTED, SECRET_PATTERN, ExecutionDependencies
from common.base import Contract
from common.execution import RequestContext

OUTPUT_LIMIT = 65_536


class CommandRequest(Contract):
    argv: tuple[str, ...] = Field(min_length=1)
    cwd: str | None = None
    timeout_seconds: float = Field(default=20.0, gt=0, le=900)


class CommandResult(Contract):
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False


SPEC = CapabilitySpec.model_validate(
    {
        "identity": {"namespace": "system", "name": "run-command", "version": "1.0.0"},
        "name": "system.run_command",
        "description": (
            "Execute an argv command under the host OS account, including package installers. "
            "No shell interpolation. Returns actual exit code and bounded output; "
            "OS/service permissions apply."
        ),
        "input_contract": "system.run-command.input.v1",
        "output_contract": "system.run-command.output.v1",
        "side_effect": "execute",
        "policy": {"required_permissions": [], "policy_refs": []},
    }
)


async def _drain(stream: asyncio.StreamReader | None) -> tuple[str, bool]:
    if stream is None:
        return "", False
    kept = bytearray()
    total = 0
    while chunk := await stream.read(8192):
        total += len(chunk)
        kept.extend(chunk[: max(0, OUTPUT_LIMIT - len(kept))])
    return SECRET_PATTERN.sub(REDACTED, kept.decode("utf-8", errors="replace")), total > len(kept)


async def execute(context: RequestContext, inputs: Contract) -> Contract:
    request = CommandRequest.model_validate(inputs)
    try:
        process = await asyncio.create_subprocess_exec(
            *request.argv,
            cwd=request.cwd,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
    except PermissionError:
        raise CapabilityRefused("environment_denied") from None
    except FileNotFoundError:
        raise CapabilityRefused("executable_not_found") from None
    except OSError:
        raise CapabilityRefused("process_start_failed") from None
    stdout = asyncio.create_task(_drain(process.stdout))
    stderr = asyncio.create_task(_drain(process.stderr))
    timed_out = False
    try:
        try:
            await asyncio.wait_for(process.wait(), request.timeout_seconds)
        except TimeoutError:
            timed_out = True
        finally:
            if process.returncode is None:
                if os.name == "nt":
                    # A venv launcher can have a child holding the output pipes.
                    # Terminate this command's tree, not just its launcher.
                    try:
                        await asyncio.to_thread(
                            subprocess.run,
                            [
                                os.path.join(
                                    os.environ.get("SystemRoot", r"C:\Windows"),
                                    "System32",
                                    "taskkill.exe",
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
                if process.returncode is None:
                    process.kill()
                await process.wait()
    except BaseException:
        stdout.cancel()
        stderr.cancel()
        await asyncio.gather(stdout, stderr, return_exceptions=True)
        raise
    out, err = await asyncio.gather(stdout, stderr)
    result = CommandResult(
        exit_code=process.returncode,
        stdout=out[0],
        stderr=err[0],
        timed_out=timed_out,
        stdout_truncated=out[1],
        stderr_truncated=err[1],
    )
    if timed_out or process.returncode != 0:
        raise CapabilityExecutionFailed(
            "command_timeout" if timed_out else "command_failed", result
        )
    return result


def register(installed: InstalledCapabilities) -> None:
    installed.register(
        SPEC,
        execute,
        CommandRequest,
        CommandResult,
        ExecutionDependencies(central_required=False),
        timeout_seconds=910,
    )
