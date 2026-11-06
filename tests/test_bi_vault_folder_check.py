"""The vault form's folder, checked as typed, with this PC's OneDrive to pick (acceptance F3).

There is no folder dialog: the page runs in a browser and AEP cannot show one there.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from test_bi_vault import _call, _ok, _two_pcs

from host_runtime.bi_cards_api import route


def _check(ws: Path, path: str, mode: str = "new") -> dict[str, Any]:
    query = {"path": path, "mode": mode}
    return dict(_ok(route(ws, "tester", "GET", "/api/bi/vaults/folder-check", query, None)))


@pytest.fixture
def onedrive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    profile = tmp_path / "profile"
    company = profile / "OneDrive - Fake Co"
    company.mkdir(parents=True)
    (profile / "OneDrive").mkdir()
    for name in ("OneDriveCommercial", "OneDrive", "OneDriveConsumer"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OneDriveCommercial", str(company))
    monkeypatch.setenv("USERPROFILE", str(profile))
    monkeypatch.setenv("HOME", str(profile))
    return company


def test_a_typed_folder_says_whether_it_can_be_used(tmp_path: Path, onedrive: Path) -> None:
    _drive, vault_id, _dataset, a, _b = _two_pcs(tmp_path)
    suggest = [str(onedrive), str(onedrive.parent / "OneDrive")]
    assert _check(a, "")["suggest"] == suggest
    assert "完整的資料夾路徑" in _check(a, "relative\\folder")["problem"]
    missing = _check(a, str(tmp_path / "nowhere"))
    assert not missing["ok"] and "找不到資料夾" in missing["problem"]

    elsewhere = _check(a, str(tmp_path))
    assert elsewhere["ok"] and not elsewhere["shared"]
    inside = onedrive / "BI"
    inside.mkdir()
    assert _check(a, str(inside))["shared"]

    # Joining needs a vault there, not just a folder.
    assert "不是 BI 知識庫" in _check(a, str(tmp_path), "join")["problem"]
    folder = Path(_ok(_call(a, "GET", f"/api/bi/vaults/{vault_id}/status"))["vault"]["path"])
    assert _check(a, str(folder), "join")["ok"]
