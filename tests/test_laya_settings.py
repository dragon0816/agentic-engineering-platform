"""The Settings page's Laya card and the SSH tunnel Agent Web keeps (owner, 2026-10-13)."""

from __future__ import annotations

import io
import json
import threading
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from test_host_wiring import host_json, ready

from agent.decisions import AcceleratorEgressApproval, DecisionAcceleratorConfig
from common.assets import SecretRef
from host_runtime.contracts import CompanyHostConfiguration, LayaSettings
from host_runtime.host import build_runtime
from host_runtime.laya import (
    LayaError,
    SshTunnel,
    accelerator_for,
    current_settings,
    last_decision,
    probe,
    ssh_config_host,
    tunnel_command,
)
from host_runtime.web import AgentWeb
from host_runtime.web_page import PAGE

SETTINGS = LayaSettings(ssh_host="172.25.228.141", ssh_port=2222, ssh_user="openlab",
                        mode="shadow", approval_ref="owner-approved-2026-10-05-laya-shadow")
SHADOW = DecisionAcceleratorConfig(
    provider="JEV", endpoint="http://127.0.0.1:18000/v1/systemone",
    credential=SecretRef(name="jev_api_key"), model_profile="laya-rl-agent", timeout_ms=1500,
    enabled_decision_types=("skill_selection",), mode="shadow", skill_max_tools=3,
    egress_approval=AcceleratorEgressApproval(approval_ref="owner-approved-2026-10-05"))


def test_host_and_account_can_never_become_ssh_options() -> None:
    for bad in ({"ssh_host": "-oProxyCommand=calc"}, {"ssh_host": "a b"},
                {"ssh_user": "-l root"}, {"ssh_user": "x;y"},
                {"auto_tunnel": True}, {"approval_ref": " "}, {"local_port": 80}):
        with pytest.raises(ValidationError):
            LayaSettings.model_validate(bad)
    command = tunnel_command(SETTINGS, "ssh")
    assert command[-2:] == ["--", "172.25.228.141"]  # nothing after `--` is an option
    assert "BatchMode=yes" in command and "ExitOnForwardFailure=yes" in command
    assert command[command.index("-L") + 1] == "127.0.0.1:18000:127.0.0.1:8000"
    assert command[command.index("-p") + 1] == "2222"


def test_the_card_derives_a_loopback_accelerator_and_keeps_hidden_fields() -> None:
    credentials = {"jev_api_key": "AEP_JEV_API_KEY"}
    assert accelerator_for(SETTINGS.model_copy(update={"mode": "off"}), SHADOW,
                           credentials) == DecisionAcceleratorConfig()
    active = accelerator_for(SETTINGS.model_copy(update={"mode": "active", "local_port": 18100,
                                                         "confidence_threshold": 0.95}),
                             SHADOW, credentials)
    assert active.endpoint == "http://127.0.0.1:18100/v1/systemone"
    assert (active.mode, active.confidence_threshold, active.skill_max_tools) == (
        "active", 0.95, 3)
    assert active.egress_approval is not None
    assert active.egress_approval.approval_ref == SETTINGS.approval_ref
    with pytest.raises(LayaError, match="egress_approval_missing"):
        accelerator_for(SETTINGS.model_copy(update={"approval_ref": None}), SHADOW, credentials)
    with pytest.raises(LayaError, match="credential_unmapped"):
        accelerator_for(SETTINGS, DecisionAcceleratorConfig(), {})


def test_first_values_come_from_host_json_and_the_ssh_config(tmp_path: Path) -> None:
    config_file = tmp_path / "config"
    config_file.write_text("Host proxy\n    HostName 1.2.3.4\nHost laya\n"
                           "    HostName 172.25.228.141\n    Port 2222\n    User openlab\n"
                           "    IdentityFile ~/.ssh/k\n"
                           "    LocalForward 18000 127.0.0.1:8000\n", encoding="utf-8")
    assert ssh_config_host(config_file) == {
        "ssh_host": "172.25.228.141", "ssh_port": 2222, "ssh_user": "openlab",
        "local_port": 18000, "remote_port": 8000}
    config, _ = ready(tmp_path, config_changes={
        "decision_accelerator": json.loads(SHADOW.model_dump_json()),
        "credentials": [{"secret": "jev_api_key", "environment_variable": "AEP_JEV_API_KEY"}]})
    seeded = current_settings(config, config_file)
    assert (seeded.ssh_host, seeded.mode, seeded.approval_ref) == (
        "172.25.228.141", "shadow", "owner-approved-2026-10-05")


class _Process:
    def __init__(self, stderr: bytes) -> None:
        self.stderr = io.BytesIO(stderr)
        self.pid, self.returncode = 4242, 255

    def wait(self) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode

    def terminate(self) -> None:
        pass


def test_a_refused_key_is_shown_and_the_tunnel_is_retried() -> None:
    calls: list[list[str]] = []
    done = threading.Event()

    def popen(command: list[str], **_: Any) -> _Process:
        calls.append(command)
        return _Process(b"openlab@172.25.228.141: Permission denied (publickey).\n")

    def sleep(_: float) -> None:
        if len(calls) >= 2:
            tunnel.stop()
            done.set()

    tunnel = SshTunnel(SETTINGS, popen=popen, ssh="ssh", sleep=sleep, bind=lambda pid: None)
    tunnel.start()
    assert done.wait(5)
    assert len(calls) == 2 and tunnel.restarts == 2
    assert tunnel.error == "openlab@172.25.228.141: Permission denied (publickey)."


def test_probe_and_last_decision(tmp_path: Path) -> None:
    assert probe(1, timeout=0.5)["reachable"] is False
    log = tmp_path / "jev-shadow.jsonl"
    log.write_text('{"kind":"shadow","at":"2026-10-13T00:00:00","outcome":"would_select",'
                   '"latency_ms":301.2}\n{"kind":"turn","status":"answered"}\n', encoding="utf-8")
    assert last_decision(log) == {"at": "2026-10-13T00:00:00", "outcome": "would_select",
                                  "latency_ms": 301.2}
    assert last_decision(tmp_path / "none.jsonl") is None


def test_saving_the_card_writes_host_json(tmp_path: Path) -> None:
    config, layout = ready(tmp_path, config_changes={"credentials": [
        {"secret": "jev_api_key", "environment_variable": "AEP_JEV_API_KEY"}]})
    path = host_json(tmp_path, config)
    with build_runtime(config, layout=layout) as runtime:
        web = AgentWeb(runtime, config_path=path)
        refused = web.update_laya({**SETTINGS.model_dump(mode="json"), "approval_ref": None})
        assert refused == {"ok": False, "code": "egress_approval_missing"}
        assert web.update_laya({"ssh_host": "-oX"})["code"] == "laya_settings_invalid"
        saved = web.update_laya(SETTINGS.model_dump(mode="json"))
        assert saved["ok"] and saved["restart_required"] and saved["running_mode"] == "off"
        written = CompanyHostConfiguration.model_validate_json(path.read_text("utf-8"))
        assert written.laya == SETTINGS
        assert written.decision_accelerator.endpoint == "http://127.0.0.1:18000/v1/systemone"
        assert written.decision_accelerator.mode == "shadow"
        assert getattr(web, "laya_tunnel", None) is None  # auto_tunnel is off
        assert AgentWeb(runtime).update_laya({}) == {"ok": False, "code": "settings_read_only"}


def test_the_settings_page_has_the_laya_card() -> None:
    for hook in ('id="laya-settings"', 'id="laya-host"', 'id="laya-auto"', 'id="laya-mode"',
                 "/api/settings/laya", 'id="laya-status"'):
        assert hook in PAGE
