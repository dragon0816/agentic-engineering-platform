"""Installed built-ins are discoverable before a Skill or Workflow references them."""

from pathlib import Path
from typing import Any

import pytest
from test_host_wiring import authorization, host_json, membership_record, ready, workspace

from host_runtime.cli import main
from host_runtime.host import build_runtime
from integrations import outlook_mail


def test_outlook_discovery_needs_no_referencing_workflow_or_com(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config, layout = ready(tmp_path)

    def no_com(*args: Any, **kwargs: Any) -> Any:
        pytest.fail("tool discovery must not initialize or read Outlook")

    monkeypatch.setattr(outlook_mail, "require_com", no_com)
    monkeypatch.setattr(outlook_mail.OutlookComMailbox, "__init__", no_com)
    with build_runtime(config, layout=layout) as runtime:
        installed = runtime.agent.gateway.bridge.installed
        targets = {item.identity.key for item in installed.discover()}
    for name in ("search", "read", "draft"):
        assert ("outlook", name, "1.0.0") in targets


def test_data_and_bi_tools_do_not_need_a_procedure_skill(tmp_path: Path) -> None:
    config, layout = ready(tmp_path)
    with build_runtime(config, layout=layout) as runtime:
        targets = {item.identity.key for item in runtime.agent.gateway.bridge.installed.discover()}
    assert ("bi-cards", "query", "1.0.0") in targets
    assert ("business-cards", "find", "1.0.0") in targets


def test_local_assets_are_usable_without_member_tool_selections(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    import json

    config, layout = workspace(tmp_path, membership=membership_record())
    layout.authorization.write_text(json.dumps(authorization("capability")), encoding="utf-8")
    target = layout.workspace_root / "notes.txt"
    assert main(["ask", "--config", str(host_json(tmp_path, config)), f"files.read {target}"]) == 0
    assert "succeeded, 1 step(s) completed" in capsys.readouterr().out
