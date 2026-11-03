"""What a new install approves for the built-in gateway (owner 2026-11-03):
internal data goes to the model service by default on a new install, and an
update never rewrites the approval of a host that already has a model."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest

from capabilities.bi_cards.ai_runs import AiRuntime, check_classification
from capabilities.bi_cards.store import BiStoreError

TEMPLATE = Path(__file__).resolve().parents[1] / "deploy" / "windows-preview"


def _fragment() -> dict[str, Any]:
    return dict(json.loads((TEMPLATE / "gateway-default.json").read_text(encoding="utf-8")))


def _approved() -> tuple[str, ...]:
    return tuple(_fragment()["models"]["data_approval"]["approved_classes"])


def test_a_new_install_approves_internal_and_nothing_higher() -> None:
    assert set(_approved()) == {"UNCLASSIFIED", "INTERNAL"}
    ai = AiRuntime(model=lambda: None, background=lambda _t, _w: None, approved=_approved)
    check_classification(ai, "INTERNAL")
    check_classification(ai, "UNCLASSIFIED")
    for level in ("CONFIDENTIAL", "RESTRICTED"):
        with pytest.raises(BiStoreError) as refused:
            check_classification(ai, level)
        assert refused.value.code == "classification_not_approved"


def test_the_installer_takes_the_approval_from_that_file_and_update_runs_the_installer() -> None:
    installer = (TEMPLATE / "install.ps1").read_text(encoding="utf-8")
    assert 'Join-Path $BundleRoot "gateway-default.json"' in installer
    assert "$Config.models = $Fragment.models" in installer
    assert '(Join-Path $PSScriptRoot "install.ps1")' in (TEMPLATE / "update.ps1").read_text(
        encoding="utf-8"
    )


def _merged(install_root: Path) -> dict[str, Any]:
    """Run the installer's host.json merge on its own, as Windows PowerShell
    runs it: an update goes through this same block."""
    text = (TEMPLATE / "install.ps1").read_text(encoding="utf-8")
    block = text[
        text.index('$ConfigPath = Join-Path $InstallRoot "host.json"') : text.index(
            "# PLATFORM-CREDENTIALS-BEGIN"
        )
    ]
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$InstallRoot = '{install_root}'\n"
        f"$BundleRoot = '{TEMPLATE}'\n"
        "$FixedNamespace = 'engineering'\n"
        "$NoGateway = $false\n"
        "$Config = [ordered]@{}\n"
        f"{block}\n"
        "Write-Output ('JSON:' + ($Config | ConvertTo-Json -Depth 12 -Compress))\n"
    )
    done = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "-"],
        input=script,
        capture_output=True,
        text=True,
        timeout=120,
        check=True,
    )
    [line] = [item for item in done.stdout.splitlines() if item.startswith("JSON:")]
    return dict(json.loads(line[len("JSON:") :]))


@pytest.mark.skipif(shutil.which("powershell.exe") is None, reason="needs Windows PowerShell")
def test_a_new_install_writes_the_approval_and_an_update_keeps_an_existing_one(
    tmp_path: Path,
) -> None:
    fresh = _merged(tmp_path)
    assert fresh["models"]["data_approval"]["approved_classes"] == list(_approved())

    # A host installed earlier: its own approval, without INTERNAL.
    existing = _fragment()
    earlier = existing["models"]["data_approval"]
    earlier["approved_classes"] = ["UNCLASSIFIED"]
    earlier["approval_ref"] = "owner-approved/localhost-litellm-2026-10-02"
    (tmp_path / "host.json").write_text(json.dumps(existing), encoding="utf-8")
    updated = _merged(tmp_path)
    assert updated["models"]["data_approval"]["approved_classes"] == ["UNCLASSIFIED"] or (
        updated["models"]["data_approval"]["approved_classes"] == "UNCLASSIFIED"
    )
    assert (
        updated["models"]["data_approval"]["approval_ref"]
        == "owner-approved/localhost-litellm-2026-10-02"
    )
