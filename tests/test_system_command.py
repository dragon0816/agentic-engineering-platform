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
