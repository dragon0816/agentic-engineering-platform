"""The 分享 step at the end of step 3, in a real browser on fictional data (acceptance F13-F15,
`docs/phases/BI_PAGE_SIMPLE.md` S6).

One table of what will be shared, each domain's test state, a tag name proposed from today's
date, then one button: commit, push, tag and publish in order, stopping at the first failure
and saying what is done and what is not. A regression in another domain does not stop it; one
in the domain it touches does. Every confirm is the page's own, and each table's common
actions are buttons in the row.
"""

from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok
from test_bi_working_domain_ui import AIDC, WIRELESS, _question, _skill
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards import vault
from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore
from host_runtime import bi_bench

# Counts the browser's own dialogs: the page must not use them.
_NO_DIALOGS = (
    "window.__dialogs = 0;"
    " window.confirm = () => { window.__dialogs += 1; return true; };"
    " window.alert = () => { window.__dialogs += 1; };"
)


def _ask(wrong: str) -> Any:
    def ask(question: str, side: bi_bench.Side) -> dict[str, Any]:
        bad = side == "working" and wrong in question
        return {"ok": True, "answer": "不知道" if bad else "好"}

    return ask


def _states(page: BiPage) -> dict[str, str]:
    return dict(
        json.loads(
            page.run(
                "JSON.stringify(Object.fromEntries([...document.querySelectorAll("
                "'#bi-b-share-tests tbody tr')].map((r) => [r.cells[0].textContent,"
                " r.cells[1].querySelector('.bi-badge').textContent])))"
            )
        )
    )


def _progress(page: BiPage) -> dict[str, str]:
    return dict(
        json.loads(
            page.run(
                "JSON.stringify(Object.fromEntries([...document.querySelectorAll("
                "'#bi-b-share-progress li')].map((li) => [li.dataset.step, li.dataset.state])))"
            )
        )
    )


def _in_sight(page: BiPage, scope: str, label: str) -> bool:
    """A button with this label in the row itself, not inside a closed menu."""
    return bool(
        page.run(
            f"[...document.querySelectorAll({json.dumps(scope + ' button')})]"
            f".some((b) => b.textContent === {json.dumps(label)} && !b.closest('details'))"
        )
    )


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_one_share_step_carries_commit_push_tag_and_publish(tmp_path: Path) -> None:
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
            {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
             "author": "alice"},
        )
    )  # fmt: skip
    dataset, vault_id = str(made["vault"]["dataset"]), str(made["vault"]["id"])
    path = f"/api/bi/vaults/{vault_id}"
    staging = Staging(workspace, dataset)
    staging.add_source("wl.md", text="# WL\n", actor="alice", folder=WIRELESS)
    staging.add_source("aidc.md", text="# AIDC\n", actor="alice", folder=AIDC)
    _skill(workspace, vault_id, "aidc-rule", AIDC)
    _question(workspace, vault_id, "mine", "aidc")
    _question(workspace, vault_id, "theirs", "wireless")
    _ok(_call(workspace, "POST", f"{path}/commit", {"purpose": "題目與規則"}))
    assert _ok(_call(workspace, "POST", f"{path}/push", {}))["status"] == "pushed"
    # A whole-vault run with a wireless regression; then a new aidc question, not committed.
    bi_bench.run(workspace, vault_id, ask=_ask("theirs"), extract=lambda c: [], actor="alice")
    _question(workspace, vault_id, "mine-2", "aidc")
    today = date.today().isoformat()

    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "share" if shots else None
        ) as page:
            page.run(_NO_DIALOGS)
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=build]")
            page.stage("test")
            page.wait("document.querySelectorAll('#bi-b-share-tests tbody tr').length === 2")
            label = "bi.build.homes.find((h) => h.home === %r).label"
            wireless, aidc = str(page.run(label % "wireless")), str(page.run(label % "aidc"))

            # -- what will be shared, by whom, in which domain ---------------------------------
            rows = json.loads(
                page.run(
                    "JSON.stringify([...document.querySelectorAll('#bi-b-share-list tbody tr')]"
                    ".map((r) => [r.cells[0].querySelector('strong').textContent,"
                    " ...[...r.cells].slice(1).map((c) => c.textContent)]))"
                )
            )
            assert rows[0][0] == "還沒 commit 的改動 1 項" and rows[0][2] == aidc
            assert ["題目與規則", "alice", "全部領域", "已 push"] in rows, rows
            # Each domain's tests: wireless regressed, aidc's content changed since its run.
            assert _states(page) == {aidc: "沒有測試", wireless: "退步"}
            tests = page.text_of("bi-b-share-tests")
            assert "其他領域，不擋這次 push" in tests and "虛構題 theirs" in tests
            # A regression in another domain does not stop it, and asks nothing more.
            assert not page.run("document.getElementById('bi-b-share-go').disabled")
            assert page.run("document.getElementById('bi-b-share-tag').value") == today
            page.run("document.getElementById('bi-b-ver').scrollIntoView(); 0")
            page.shoot("share-before")

            # -- the first failure stops it, saying what is done and what is not ---------------
            # A colleague took today's name after the page proposed it.
            _ok(_call(workspace, "POST", f"{path}/tag", {"name": today, "purpose": "別人的"}))
            page.click("#bi-b-share-go")
            page.notice("請先寫這次改動的目的")
            assert page.run("!document.querySelector('#bi-b-share-act .bi-confirm')")
            page.set_value("bi-b-ver-purpose", "aidc 的新題目")
            page.click("#bi-b-share-go")
            page.wait("!!document.querySelector('#bi-b-share-act .bi-confirm')")
            confirm = page.text_of("bi-b-share-act")
            assert "commit 1 項改動、push、建立 tag「" + today + "」並發佈" in confirm
            page.click_text("#bi-b-share-act .bi-confirm", "取消")
            assert page.run("!document.querySelector('#bi-b-share-act .bi-confirm')")
            assert page.run("document.getElementById('bi-b-share-progress').hidden")

            page.click("#bi-b-share-go")
            page.click_text("#bi-b-share-act .bi-confirm", "確定分享")
            page.notice("分享停在「建立 tag」")
            notice = page.text_of("bi-notice")
            assert "已完成：Commit、Push 給大家；沒有做：建立 tag、發佈。" in notice, notice
            assert "已經存在" in notice
            assert _progress(page) == {
                "commit": "done",
                "push": "done",
                "tag": "failed",
                "publish": "waiting",
            }
            assert "沒有做" in page.run(
                "document.querySelector('#bi-b-share-progress li[data-step=publish]').textContent"
            )
            target = vault.Vault(workspace, vault_id)
            assert target.status()["ahead"] == 0 and target.status()["uncommitted"] == 0
            assert target.reads()["tag"] is None
            page.run("document.getElementById('bi-b-ver').scrollIntoView(); 0")
            page.shoot("share-stopped")

            # -- pressed again: the taken name gets a suffix, and it finishes ------------------
            page.wait(
                "document.getElementById('bi-b-share-tag').value === " + json.dumps(today + "-2")
            )
            page.see("bi-b-share-list", "aidc 的新題目")
            page.click("#bi-b-share-go")
            page.click_text("#bi-b-share-act .bi-confirm", "確定分享")
            page.wait(
                "document.querySelector('#bi-b-share-progress li[data-step=publish]')"
                ".dataset.state === 'done'"
            )
            assert _progress(page) == {
                "commit": "skipped",
                "push": "done",
                "tag": "done",
                "publish": "done",
            }
            page.see("bi-b-ver-reads", "發佈版本「" + today + "-2」")
            page.see("bi-b-share-list", "沒有新的內容")
            assert page.run("document.getElementById('bi-b-share-go').disabled")
            assert vault.Vault(workspace, vault_id).reads()["tag"] == today + "-2"

            # -- 進階: the history keeps 看改動 and 發佈 in the row, with the page's confirm ---
            page.wait(
                "[...document.querySelectorAll('#bi-b-ver-history button')]"
                f".some((b) => b.textContent === {json.dumps('發佈 ' + today)})"
            )
            assert _in_sight(page, "#bi-b-ver-history tbody tr:first-child", "看改動")
            assert _in_sight(page, "#bi-b-ver-history", "發佈 " + today)
            assert not _in_sight(page, "#bi-b-ver-history", "加 tag")  # rarer: in 更多
            assert _in_sight(page, "#bi-b-sk-list", "修改")
            assert _in_sight(page, "#bi-b-sk-list", "和 AI 一起修改")
            publish = (
                "[...document.querySelectorAll('#bi-b-ver-history button')]"
                f".find((b) => b.textContent === {json.dumps('發佈 ' + today)}).click()"
            )
            page.run(publish)
            page.wait("!!document.querySelector('#bi-b-ver-history .bi-confirm')")
            page.click_text("#bi-b-ver-history .bi-confirm", "取消")
            assert vault.Vault(workspace, vault_id).reads()["tag"] == today + "-2"
            page.run(publish)
            page.click_text("#bi-b-ver-history .bi-confirm", "確定發佈")
            page.see("bi-b-ver-reads", "發佈版本「" + today + "」")

            # -- 進階: discard asks on the page too -------------------------------------------
            _question(workspace, vault_id, "later", "aidc")
            page.run("biVersions(bi.verVault)")
            page.wait("!document.getElementById('bi-b-ver-discard').disabled")
            page.click("#bi-b-ver-discard")
            page.wait("!!document.querySelector('#bi-b-adv-ver .bi-confirm')")
            page.click_text("#bi-b-adv-ver .bi-confirm", "確定捨棄")
            page.notice("已捨棄")
            assert vault.Vault(workspace, vault_id).status()["uncommitted"] == 0

            # -- a regression in the domain it touches still blocks ---------------------------
            _question(workspace, vault_id, "theirs-2", "wireless")
            bi_bench.run(workspace, vault_id, ask=_ask("theirs"), extract=lambda c: [], actor="a")
            page.run("biVersions(bi.verVault)")
            page.wait("document.getElementById('bi-b-share-go').disabled")
            assert "測試退步" in page.text_of("bi-b-share-why")
            assert "（wireless）" in page.text_of("bi-b-share-tests")
            page.run("document.getElementById('bi-b-ver').scrollIntoView(); 0")
            page.shoot("share-blocked")
            assert page.run("window.__dialogs") == 0
