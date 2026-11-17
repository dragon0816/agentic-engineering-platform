"""Schema overlaps and skill flags in the page (`BI_CARD_MODEL.md` §4.3). A real browser on
fictional data: a change that landed and no longer fits is in the push conflict list, and a
skill an addition touches says it keeps working."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.cards import vault
from aep_bi.cards.store import BiStore

CLASH = "schema_change:enum:Technology.no_such_field:pilot"
COOLING = {"kind": "str", "class": "sourced", "label": "冷卻方式"}


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_clash_is_in_the_push_list_and_an_addition_says_the_rule_keeps_working(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    BiStore(workspace, "demo").create("bi.schema/v1.1")
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(
        _call(
            workspace,
            "POST",
            "/api/bi/vaults",
            {
                "path": str(shared),
                "title": "Market",
                "schema": "bi.schema/v1.1",
                "author": "alice",
            },
        )
    )
    dataset, vault_id = str(made["vault"]["dataset"]), str(made["vault"]["id"])
    rule = {
        "name": "wireless/uses-tech",
        "role": "extract",
        "body": "只讀技術。",
        "card_types": ["Technology"],
    }
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/skills", rule))
    target = vault.Vault(workspace, vault_id)
    with target.lock:
        target.repo.stage("schema_change:field:Technology.cooling", COOLING)
        target.repo.stage(CLASH, {"value": "pilot"})
        target.rebuild()
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "schema" if shots else None
        ) as page:
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            box = "document.getElementById('bi-b-ver-conflicts')"
            page.wait(f"{box}.textContent.includes('no_such_field')")
            listed = page.text_of("bi-b-ver-conflicts")
            assert "schema 的改動有 1 個要決定" in listed
            assert "已經不在這個版本" in listed
            assert page.run(f"{box}.getAttribute('role')") == "alert"
            page.shoot("clash")

            skills = "document.getElementById('bi-b-sk-list')"
            page.wait(f"{skills}.textContent.includes('uses-tech')")
            shown = page.text_of("bi-b-sk-list")
            assert "可以看一下" in shown and "cooling" in shown and "規則照常可以用" in shown
            assert "修改並儲存後才會再使用" not in shown

            page.click_text("#bi-b-ver-conflicts", "放棄這個改動")
            page.wait(f"!{box}.textContent.includes('no_such_field')")
            page.see("bi-notice", "已放棄這個改動")
            page.shoot("decided")
    assert CLASH not in target.repo.working_units()
