"""Real local processes, without packages, network or external system writes."""

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest
from test_dispatch import invocation

from agent.gateway import HostToolOutcome
from capabilities.runtime import InstalledCapabilities
from capabilities.system_command.handlers import register
from host_runtime.tool_access import ToolAccess
from workflow.dispatch import BridgeExecutor


def run(code: str, **arguments: Any) -> HostToolOutcome:
    installed = InstalledCapabilities()
    register(installed)
    return asyncio.run(
        ToolAccess(BridgeExecutor(installed)).invoke(
            invocation().context,
            "system/run-command@1.0.0",
            {"argv": [sys.executable, "-c", code], **arguments},
        )
    )


def data(outcome: HostToolOutcome) -> dict[str, Any]:
    assert isinstance(outcome.data, dict)
    result = outcome.data["result"]
    assert isinstance(result, dict)
    return result


def test_local_command_has_real_output_without_application_approval(tmp_path: Path) -> None:
    result = run("import os; print(os.getcwd())", cwd=str(tmp_path))
    assert result.status == "succeeded"
    assert data(result)["exit_code"] == 0
    assert data(result)["stdout"].strip() == str(tmp_path)


def test_nonzero_preserves_failure_and_diagnostics() -> None:
    result = run("import sys; print('fixture'); sys.exit(7)")
    assert result.status == "failed" and result.failure and result.failure.code == "command_failed"
    assert isinstance(result.data, dict) and result.data["handler_invoked"]
    assert data(result)["exit_code"] == 7
    assert data(result)["stdout"].strip() == "fixture"


def test_timeout_is_not_success() -> None:
    result = run("import time; time.sleep(10)", timeout_seconds=0.2)
    assert result.status == "failed" and result.failure and result.failure.code == "command_timeout"
    assert data(result)["timed_out"]


@pytest.mark.parametrize(
    "error, code",
    [(PermissionError, "environment_denied"), (FileNotFoundError, "executable_not_found")],
)
def test_os_errors_remain_real_failures(
    monkeypatch: pytest.MonkeyPatch, error: type[OSError], code: str
) -> None:
    async def denied(*args: Any, **kwargs: Any) -> Any:
        raise error("not included in the public failure")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", denied)
    result = run("print('unused')")
    assert result.status == "failed" and result.failure and result.failure.code == code
    assert "not included" not in str(result)


def test_exited_root_cannot_leave_pipe_draining_outside_the_deadline() -> None:
    from time import monotonic

    from integrations.process_execution import CommandRequest, run_command

    code = (
        "import subprocess,sys; "
        "subprocess.Popen([sys.executable,'-c','import time; time.sleep(3)']); "
        "print('root finished',flush=True)"
    )
    started = monotonic()
    result = asyncio.run(
        run_command(CommandRequest(argv=(sys.executable, "-c", code), timeout_seconds=0.5))
    )
    assert monotonic() - started < 2
    assert result.timed_out or result.exit_code == 0


def test_cancel_after_root_exit_does_not_leave_an_owned_child(tmp_path: Path) -> None:
    from integrations.process_execution import CommandRequest, run_command

    marker = tmp_path / "orphan.txt"
    child = (
        "import time; from pathlib import Path; time.sleep(1.2); "
        f"Path({str(marker)!r}).write_text('orphan')"
    )
    code = (
        f"import subprocess,sys; subprocess.Popen([sys.executable,'-c',{child!r}]); "
        "print('root finished',flush=True)"
    )

    async def scenario() -> None:
        task = asyncio.create_task(
            run_command(CommandRequest(argv=(sys.executable, "-c", code), timeout_seconds=5))
        )
        await asyncio.sleep(0.5)
        if not task.done():
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            assert task.result().exit_code == 0
        await asyncio.sleep(1.4)

    asyncio.run(scenario())
    assert not marker.exists()
