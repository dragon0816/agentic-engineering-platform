"""The default version of a shipped rule (owner 2026-11-19: 「判讀規則的skills，無法看default版
本」): the classify rule generated from the schema shows its default text, a modified one is
compared with it, and restoring it is a new revision on the person's press. All fictional."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok, _use_homes
from test_vault_asking_e2e import _bi_host, _Model, _served

AIDC = "applications/aidc/sources"


def _vault(tmp_path: Path) -> tuple[Any, Any, Path, str, str]:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(
        _call(workspace, "POST", "/api/bi/vaults",
              {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
               "author": "alice", "default_pack": False})
    )  # fmt: skip
    dataset, vault_id = str(made["vault"]["dataset"]), str(made["vault"]["id"])
    _use_homes(workspace, vault_id, "AIDC")
    return config, layout, workspace, dataset, vault_id


def _classify(ws: Path, vault_id: str) -> dict[str, Any]:
    listed = _ok(_call(ws, "GET", f"/api/bi/vaults/{vault_id}/skills"))["skills"]
    return dict(next(s for s in listed if s["name"] == "classify"))


def _edit(ws: Path, vault_id: str, body: str) -> None:
    given = {"name": "classify", "role": "classify", "body": body}
    _ok(_call(ws, "POST", f"/api/bi/vaults/{vault_id}/skills", given))


def test_the_classify_rule_shows_its_default_and_restores_it_as_a_revision(
    tmp_path: Path,
) -> None:
    _, _, ws, _, vault_id = _vault(tmp_path)
    shipped = _classify(ws, vault_id)
    assert shipped["default_body"].strip() == shipped["body"].strip()
    assert shipped["modified"] is False and shipped["generated"] is True
    _edit(ws, vault_id, shipped["body"] + "\n自己加的一行：虛構規則。")
    edited = _classify(ws, vault_id)
    assert edited["modified"] is True and edited["default_body"] == shipped["default_body"]
    revision = edited["revision"]
    # Compared with an older revision: refused, nothing overwritten unseen.
    status, stale = _call(
        ws, "POST", f"/api/bi/vaults/{vault_id}/skill-default",
        {"name": "classify", "revision": revision - 1},
    )  # fmt: skip
    assert (status, stale["code"]) == (409, "skill_changed")
    restored = _ok(
        _call(ws, "POST", f"/api/bi/vaults/{vault_id}/skill-default",
              {"name": "classify", "revision": revision})
    )  # fmt: skip
    assert restored["skill"]["revision"] == revision + 1
    back = _classify(ws, vault_id)
    assert back["revision"] == revision + 1 and back["modified"] is False
    assert back["generated"] is True, "generated again on the next schema change"
    status, none = _call(
        ws, "POST", f"/api/bi/vaults/{vault_id}/skill-default", {"name": "aidc/x", "revision": 1}
    )
    assert (status, none["code"]) == (400, "skill_no_default")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_rule_table_shows_the_default_beside_a_modified_rule(tmp_path: Path) -> None:
    config, layout, ws, dataset, vault_id = _vault(tmp_path)
    shipped = _classify(ws, vault_id)
    _edit(ws, vault_id, shipped["body"] + "\n自己加的一行：虛構規則。")
    revision = _classify(ws, vault_id)["revision"]
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait("!document.getElementById('bi-b-src-folder-box').hidden")
            page.choose("bi-b-src-folder", AIDC)
            page.stage("schema")
            page.see("bi-b-sk-list", "和預設不同")
            page.click_text("#bi-b-sk-list", "預設版本")
            page.see("bi-b-sk-list", "標色的行只在其中一邊")
            marked = page.run(
                "[...document.querySelectorAll('#bi-b-sk-list .bi-sk-diff')]"
                ".map((s) => s.textContent.trim())"
            )
            assert marked == ["自己加的一行：虛構規則。"]
            page.click_text("#bi-b-sk-list", "恢復成預設")
            page.notice(f"存成第 {revision + 1} 版")
            page.see("bi-b-sk-list", "依 schema 產生")
            assert "和預設不同" not in page.text_of("bi-b-sk-list")
            # The default of a rule nobody changed is just shown.
            page.click_text("#bi-b-sk-list", "預設版本")
            page.see("bi-b-sk-list", "現在用的就是預設版本")
    assert json.dumps(_classify(ws, vault_id)["modified"]) == "false"
