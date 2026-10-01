"""Governed Python and PowerShell tools stay behind the normal Bridge policy."""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from pydantic import ValidationError
from test_host_wiring import grant_record, membership_record, workspace

from capabilities.runtime import CapabilityRefused
from capabilities.script_tools import (
    ProcessRunner,
    ScriptToolHandler,
    ScriptToolInput,
    ScriptToolManifest,
    load_script_tools,
)
from common.assets import AssetIdentity
from common.execution import RequestContext, TraceIdentifiers
from common.local_agent import LocalCapabilityRequest
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb

IDENTITY = AssetIdentity(namespace="engineering", name="json-echo", version="1.0.0")
TRACE = TraceIdentifiers(
    trace_id="trace-script", request_id="request-script", span_id="span-script"
)


def policy() -> dict[str, Any]:
    return {
        "status": "approved",
        "reviewer": "security-reviewer",
        "evidence": "Reviewed fixed JSON process boundary.",
        "risk": "medium",
        "approval_required": True,
        "required_permissions": ["scripts.execute"],
        "policy_refs": ["script-execution-policy"],
        "assessment": "manual",
    }


def manifest(runtime: str, entrypoint: str, digest: str) -> dict[str, Any]:
    technical = policy()
    return {
        "metadata": {
            "identity": IDENTITY.model_dump(mode="json"),
            "owner": {"type": "team", "id": "engineering"},
            "visibility": "private",
            "lifecycle": "published",
            "business_approval": {
                "status": "approved",
                "reviewer": "domain-owner",
                "evidence": "Fixture behavior reviewed.",
            },
            "technical_policy": technical,
        },
        "description": "Echo one JSON value through a governed process.",
        "runtime": runtime,
        "entrypoint": entrypoint,
        "sha256": digest,
        "timeout_seconds": 5,
        "capability": {
            "identity": IDENTITY.model_dump(mode="json"),
            "name": "scripts.json_echo",
            "description": "Echo one JSON value.",
            "input_contract": "engineering.script-tool.input.v1",
            "output_contract": "engineering.script-tool.output.v1",
            "side_effect": "execute",
            "policy": technical,
        },
        "dependencies": {"central_required": False},
    }


def write_package(root: Path, *, runtime: str = "python", payload: str | None = None) -> Path:
    package = root / IDENTITY.namespace / IDENTITY.name / IDENTITY.version
    package.mkdir(parents=True)
    if runtime == "python":
        entrypoint = "main.py"
        source = payload or (
            "import json, sys\n"
            "value = json.load(sys.stdin)\n"
            "json.dump({'echo': value['value']}, sys.stdout)\n"
        )
    else:
        entrypoint = "main.ps1"
        source = payload or (
            "$value = [Console]::In.ReadToEnd() | ConvertFrom-Json\n"
            "@{echo=$value.value} | ConvertTo-Json -Compress\n"
        )
    script = package / entrypoint
    script.write_text(source, encoding="utf-8")
    digest = hashlib.sha256(script.read_bytes()).hexdigest()
    (package / "script-tool.json").write_text(
        json.dumps(manifest(runtime, entrypoint, digest)), encoding="utf-8"
    )
    return package


def context() -> RequestContext:
    return RequestContext(
        trace=TRACE,
        actor="engineer",
        namespace="engineering",
        message="exact script fixture",
        channel="local",
    )


def test_manifest_refuses_path_escape_and_non_execute_classification() -> None:
    valid = manifest("python", "main.py", "a" * 64)
    with pytest.raises(ValidationError, match="package-relative"):
        ScriptToolManifest.model_validate({**valid, "entrypoint": "../outside.py"})
    capability = {**valid["capability"], "side_effect": "read"}
    with pytest.raises(ValidationError, match="execute side effect"):
        ScriptToolManifest.model_validate({**valid, "capability": capability})


def test_loader_rejects_hash_mismatch(tmp_path: Path) -> None:
    root = tmp_path / "script-tools"
    package = write_package(root)
    (package / "main.py").write_text("print('{}')\n", encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        load_script_tools(root)


def test_python_uses_fixed_interpreter_json_stdin_and_package_cwd(tmp_path: Path) -> None:
    root = tmp_path / "script-tools"
    package = write_package(root)
    installed = load_script_tools(root)[0]
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def runner(argv: list[str], **kwargs: Any) -> Any:
        calls.append((argv, kwargs))
        return SimpleNamespace(returncode=0, stdout='{"echo":"ok"}', stderr="ignored")

    fixed = tmp_path / "approved-python.exe"
    handler = ScriptToolHandler(installed, runner=runner, python_executable=fixed)
    output = asyncio.run(handler(context(), ScriptToolInput(arguments={"value": "ok"})))
    argv, call = calls[0]
    assert output.result == {"echo": "ok"}
    assert argv == [str(fixed.resolve()), "-I", "-S", str((package / "main.py").resolve())]
    assert json.loads(call["input"]) == {"value": "ok"}
    assert call["cwd"] == package.resolve()
    assert "GITHUB_TOKEN" not in call["env"]


def test_malformed_output_and_timeout_are_closed_codes(tmp_path: Path) -> None:
    root = tmp_path / "script-tools"
    installed = load_script_tools(root) if root.exists() else ()
    if not installed:
        write_package(root)
        installed = load_script_tools(root)

    def malformed(_argv: list[str], **_kwargs: Any) -> Any:
        return SimpleNamespace(returncode=0, stdout="not json", stderr="secret detail")

    with pytest.raises(CapabilityRefused, match="script_invalid_output"):
        asyncio.run(
            ScriptToolHandler(installed[0], runner=cast(ProcessRunner, malformed))(
                context(), ScriptToolInput(arguments={})
            )
        )

    def times_out(argv: list[str], **kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(argv, kwargs["timeout"])

    with pytest.raises(CapabilityRefused, match="script_timeout"):
        asyncio.run(
            ScriptToolHandler(installed[0], runner=cast(ProcessRunner, times_out))(
                context(), ScriptToolInput(arguments={})
            )
        )


@pytest.mark.skipif(
    shutil.which("pwsh") is None and shutil.which("powershell") is None,
    reason="PowerShell is not installed",
)
def test_powershell_fixture_uses_noninteractive_json_io(tmp_path: Path) -> None:
    root = tmp_path / "script-tools"
    installed = load_script_tools(root) if root.exists() else ()
    if not installed:
        write_package(root, runtime="powershell")
        installed = load_script_tools(root)
    result = asyncio.run(
        ScriptToolHandler(installed[0])(
            context(), ScriptToolInput(arguments={"value": "from-powershell"})
        )
    )
    assert result.result == {"echo": "from-powershell"}


def test_host_registers_script_tool_but_bridge_policy_still_decides(tmp_path: Path) -> None:
    script_grant = {
        "actor": "engineer",
        "asset": IDENTITY.model_dump(mode="json"),
        "permissions": ["scripts.execute"],
        "policy_refs": ["script-execution-policy"],
        "approval_ref": "local-script-approval",
    }
    config, layout = workspace(
        tmp_path,
        membership=membership_record(),
        grants=[*grant_record(), script_grant],
    )
    write_package(layout.script_tools)
    skill_path = layout.skills / "files.json"
    skills = json.loads(skill_path.read_text(encoding="utf-8"))
    skills[0]["script_tools"] = [IDENTITY.model_dump(mode="json")]
    skill_path.write_text(json.dumps(skills), encoding="utf-8")
    request = LocalCapabilityRequest(
        ingress="local",
        actor="engineer",
        bridge_id=config.device.bridge_id,
        target=IDENTITY,
        arguments={"arguments": {"value": "through-bridge"}},
        trace=TRACE,
    )
    with build_runtime(config) as runtime:
        script_detail = AgentWeb(runtime).assets()["skills"][0]["script_tools"][0]
        assert script_detail == {
            "identity": IDENTITY.model_dump(mode="json"),
            "description": "Echo one JSON value through a governed process.",
            "runtime": "python",
            "path": "main.py",
            "side_effect": "execute",
            "approval_required": True,
            "status": "installed",
        }
        allowed = asyncio.run(runtime.agent.execute_capability(request))
    assert allowed.capability is not None and allowed.capability.status == "succeeded"
    assert allowed.capability.data == {"result": {"echo": "through-bridge"}}

    layout.grants.write_text(json.dumps(grant_record()), encoding="utf-8")
    with build_runtime(config) as runtime:
        denied = asyncio.run(runtime.agent.execute_capability(request))
    assert denied.capability is not None and denied.capability.status == "failed"
    assert denied.capability.failure is not None
    assert denied.capability.failure.code == "permission_denied"
    assert denied.capability.handler_invoked is False
