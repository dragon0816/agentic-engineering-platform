"""A domain's own Dashboard in the page (`docs/phases/BI_PAGE_SIMPLE.md` §12).

Owner, 2026-11-05: 「每個領域也要有各自的benchmark 問題和dashboard」. It starts empty and says
what to press, a panel that shows the whole vault says so, and a switch leaves nothing of the domain
left. A real browser on fictional data.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok, _use_homes
from test_vault_asking_e2e import _bi_host, _Model, _served

AIDC = "applications/aidc/sources"
WIRELESS = "applications/wireless/sources"
BY_DOMAIN: dict[str, Any] = {
    "title": "虛構：這個領域",
    "slug": "by-domain",
    "kind": "sql",
    "code": "SELECT :domain AS d, count(*) AS n FROM cards",
    "params": {"domain": {"type": "text", "default": "x"}},
    "chart": {"type": "table"},
}
ALL_CARDS: dict[str, Any] = {
    "title": "虛構：全部",
    "slug": "all-cards",
    "kind": "sql",
    "code": "SELECT count(*) AS n FROM cards",
    "chart": {"type": "table"},
}
QUIET = "window.__aepWatch.open.length === 0"


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
@pytest.mark.parametrize("first_reply_fails", [False, True], ids=["pending-body", "failed-body"])
def test_rapid_domain_panel_adds_survive_an_unfinished_first_save(
    tmp_path: Path, first_reply_fails: bool
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(
        _call(
            workspace,
            "POST",
            "/api/bi/vaults",
            {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
             "author": "alice", "default_pack": False},
        )
    )  # fmt: skip
    dataset, vault_id = str(made["vault"]["dataset"]), str(made["vault"]["id"])
    _use_homes(workspace, vault_id, "AIDC", "Wireless")
    third = {**ALL_CARDS, "title": "Third panel", "slug": "third"}
    for item in (BY_DOMAIN, ALL_CARDS, third):
        _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/analyses", {"save": item}))
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait("(bi.build.homes || []).length > 0")
            page.stage("test")
            page.choose("bi-b-src-folder", AIDC)
            page.see("bi-b-an-state", "0 個分析")
            page.wait(QUIET, 60)
            # Headers are complete, but the first save has not consumed its JSON or refreshed.
            page.run(
                "window.__saveHold=[];window.__holdFirstSave=true;window.__dashboardPosts=0;"
                "window.__saveFetch=window.fetch;window.fetch=async(...args)=>{"
                "const saves=String(args[0]).endsWith('/analyses')"
                " && args[1] && args[1].method==='POST';if(saves)window.__dashboardPosts++;"
                "const reply=await window.__saveFetch(...args);"
                "if(window.__holdFirstSave && saves){"
                "window.__holdFirstSave=false;const read=reply.json.bind(reply);"
                "reply.json=async()=>{await new Promise(go=>window.__saveHold.push(go));"
                + ("throw new Error('controlled body failure');" if first_reply_fails else "")
                + "return read();};}return reply;};"
            )
            for index, title in enumerate((BY_DOMAIN["title"], ALL_CARDS["title"])):
                page.run(
                    "[...document.querySelectorAll('#bi-b-an-list button')]"
                    f".find(b=>b.getAttribute('aria-label')==='把分析 {title} 加到這個領域的"
                    " Dashboard').click()"
                )
                if index == 0:
                    page.wait("window.__saveHold.length===1", 60)
                    assert page.run(QUIET)
            page.run("window.__saveHold.splice(0).forEach(go=>go())")
            page.wait(page.shows("bi-b-an-state", "2 個分析"), 15)
            assert page.run("window.__dashboardPosts") == 2
            page.run("window.fetch=window.__saveFetch")
            saved = _ok(_call(workspace, "GET", f"/api/bi/vaults/{vault_id}/analyses", home="aidc"))
            assert saved["order"] == ["by-domain", "all-cards"]
            if not first_reply_fails:
                page.click('[aria-label="把分析 Third panel 加到這個領域的 Dashboard"]')
                page.see("bi-b-an-state", "3 個分析")
                page.click('[aria-label="在 Dashboard 隱藏分析 虛構：全部"]')
                page.see("bi-b-an-state", "2 個分析")
                page.click('[aria-label="在 Dashboard 上移分析 Third panel"]')
                page.wait(
                    "document.querySelector('#bi-b-an-list tbody tr strong').textContent"
                    " === 'Third panel'",
                    15,
                )
                reordered = _ok(
                    _call(workspace, "GET", f"/api/bi/vaults/{vault_id}/analyses", home="aidc")
                )
                assert reordered["order"] == ["third", "by-domain"]


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_domain_starts_empty_chooses_its_panels_and_a_switch_leaves_nothing_behind(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "shared"
    shared.mkdir()
    made = _ok(
        _call(
            workspace,
            "POST",
            "/api/bi/vaults",
            {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
             "author": "alice", "default_pack": False},
        )
    )  # fmt: skip
    dataset, vault_id = str(made["vault"]["dataset"]), str(made["vault"]["id"])
    # Only homes something is in are listed (acceptance F22): this test works in these.
    _use_homes(workspace, vault_id, "AIDC", "Wireless")
    for item in (BY_DOMAIN, ALL_CARDS):
        _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/analyses", {"save": item}))
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "dash" if shots else None
        ) as page:
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.wait("(bi.build.homes || []).length > 0")
            page.stage("test")
            page.wait(QUIET, 60)

            # -- 全部領域 is the vault's Dashboard, as ever ---------------------------------
            page.see("bi-b-an-state", "2 個分析・Dashboard 顯示 2 個")
            page.wait("document.getElementById('bi-status-dash').hidden")
            sections = page.text_of("bi-dash-sections")
            assert "虛構：全部" in sections and "全庫資料" not in sections

            # -- a domain starts empty and says what to press -------------------------------
            page.choose("bi-b-src-folder", AIDC)
            page.see("bi-b-an-state", "0 個分析")
            page.see("bi-b-an-list", "這個領域的 Dashboard 還是空的")
            page.see("bi-dash-sections", "這個領域的 Dashboard 還是空的")
            assert "虛構：全部" not in page.text_of("bi-dash-sections")
            assert not page.run("document.getElementById('bi-b-an-new').hidden")
            page.see("bi-b-an-list", "還沒放進這個領域的分析（2）")
            page.shoot("empty")

            # -- it chooses: a panel that filters, and one that shows the whole vault --------
            for title in (BY_DOMAIN["title"], ALL_CARDS["title"]):
                page.run(
                    "[...document.querySelectorAll('#bi-b-an-list button')]"
                    f".find((b) => b.getAttribute('aria-label') === '把分析 {title} 加到這個領域的"
                    " Dashboard').click()"
                )
                page.see("bi-b-an-list", title)
                page.wait(QUIET, 60)
            page.see("bi-b-an-state", "2 個分析")
            page.wait(
                "document.getElementById('bi-dash-sections').textContent.includes('虛構：這個領域')"
            )
            shown = page.text_of("bi-dash-sections")
            assert "虛構：全部（全庫資料）" in shown
            assert "虛構：這個領域（全庫資料）" not in shown
            assert "全庫資料" in page.text_of("bi-b-an-list")
            page.shoot("chosen")

            # -- saved for this domain only ---------------------------------------------------
            units = _ok(_call(workspace, "GET", f"/api/bi/vaults/{vault_id}/analyses", home="aidc"))
            assert units["order"] == ["by-domain", "all-cards"]
            other = _ok(
                _call(workspace, "GET", f"/api/bi/vaults/{vault_id}/analyses", home="wireless")
            )
            assert other["order"] == []
            whole = _ok(_call(workspace, "GET", f"/api/bi/vaults/{vault_id}/analyses"))
            assert whole["order"] == ["all-cards", "by-domain"]

            # -- a reply for the domain left does not bring its rows back --------------------
            page.wait(QUIET, 60)
            page.run(
                "(() => { const was = window.__was = window.fetch; window.__hold = [];"
                " window.fetch = async (...args) => { const reply = await was(...args);"
                " if (String(args[0]).includes('/analyses?home=aidc')) {"
                " await new Promise((go) => window.__hold.push(go)); }"
                " return reply; }; })()"
            )
            page.run("biAnalyses(bi.verVault)")
            page.wait("window.__hold.length === 1", 60)
            page.choose("bi-b-src-folder", WIRELESS)
            # At once, with the reply still held: nothing of the Dashboard just left.
            assert page.text_of("bi-b-an-state") in ("", "0 個分析")
            assert "Dashboard 第 1 個" not in page.text_of("bi-b-an-list")
            page.see("bi-b-an-state", "0 個分析")
            page.run("window.__hold.splice(0).forEach((go) => go()); window.fetch = window.__was")
            page.wait(QUIET, 60)
            assert page.text_of("bi-b-an-state").startswith("0 個分析")
            assert "這個領域的 Dashboard 還是空的" in page.text_of("bi-b-an-list")

            # -- and it comes back kept -------------------------------------------------------
            page.choose("bi-b-src-folder", AIDC)
            page.see("bi-b-an-state", "2 個分析")
