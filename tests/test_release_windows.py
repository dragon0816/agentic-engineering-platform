"""The one-command Windows release for colleagues (owner, 2026-10-13)."""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from host_runtime import launcher
from scripts.release_windows import DEPENDENCIES, MANUAL, previous_revision, release_notes

REPO = Path(__file__).resolve().parents[1]
TEMPLATE = REPO / "deploy" / "windows-preview"


def test_the_release_downloads_the_same_dependencies_as_ci() -> None:
    workflow = (REPO / ".github" / "workflows" / "verify.yml").read_text(encoding="utf-8")
    line = next(
        item
        for item in workflow.splitlines()
        if "dist/windows-preview-wheels" in item and "pip download" in item
    )
    assert tuple(re.findall(r'"([^"]+)"', line)) == DEPENDENCIES


def test_notes_list_the_commits_since_the_previous_release(tmp_path: Path) -> None:
    assert previous_revision(tmp_path) is None
    (tmp_path / "latest.json").write_text(json.dumps({"revision": "abc123"}), encoding="utf-8")
    assert previous_revision(tmp_path) == "abc123"
    notes = release_notes(
        release="20261013-1200-deadbeef",
        revision="deadbeef" * 5,
        previous="abc123",
        commits=["deadbee Fix the pull message"],
        created="2026-10-13T12:00+08:00",
    )
    assert "- deadbee Fix the pull message" in notes and "`abc123`" in notes
    tagged = release_notes(
        release="r", revision="x", previous=None, commits=[], created="t", tag="release-r"
    )
    assert "(git tag `release-r`)" in tagged
    assert "update.cmd" in notes and MANUAL in notes
    assert "(no new commits)" in release_notes(
        release="r", revision="x", previous=None, commits=[], created="t"
    )


def test_colleagues_get_a_manual_and_double_click_scripts() -> None:
    manual = (TEMPLATE / MANUAL).read_text(encoding="utf-8")
    for section in (
        "install.cmd",
        "update.cmd",
        "verify.cmd",
        "start-web.cmd",
        "uninstall.cmd -Apply",
        "Python 3.12",
        "bundle source revision",
    ):
        assert section in manual
    update = (TEMPLATE / "update.ps1").read_text(encoding="utf-8")
    assert "registered_by" in update and "bridge_id" in update  # nothing to retype
    assert "install.ps1" in update
    assert "-NoShortcut:$NoShortcut" in update  # a test install never takes over the shortcut
    installer = (TEMPLATE / "install.ps1").read_text(encoding="utf-8")
    assert "shortcut --config" in installer and "$NoShortcut" in installer
    for name in ("install.cmd", "update.cmd", "start-web.cmd"):
        assert b"\r\n" in (TEMPLATE / name).read_bytes()  # batch files need CRLF


def test_the_shortcut_carries_the_aep_icon(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[dict[str, str]] = []

    def run(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        seen.append(dict(kwargs["env"]))
        return subprocess.CompletedProcess(command, 0, "", "")

    icon = tmp_path / "aep-agent.ico"
    icon.write_bytes(b"ico")
    (tmp_path / "Desktop").mkdir()
    monkeypatch.setattr(sys, "platform", "win32")  # the sys module launcher uses
    monkeypatch.setattr(subprocess, "run", run)  # the subprocess module launcher uses
    monkeypatch.setattr(launcher, "SHORTCUT_ICON", icon)
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("APPDATA", str(tmp_path / "missing"))
    assert launcher.create_shortcuts(tmp_path / "host.json") == [
        tmp_path / "Desktop" / "AEP Agent.lnk"
    ]
    assert seen[0]["AEP_ICON"] == str(icon)
