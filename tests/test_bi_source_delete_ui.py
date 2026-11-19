"""Deleting sources in step 1, in a real browser (owner 2026-11-19).

「刪除已選（N 份）」 and a row's 「刪除」 ask once beside the control, say 「刪除中 n/N：名稱・
s 秒」 there while they work (AGENTS 23), end with what went and what stayed and why, and
redraw the table, its counts and the Markdown pane. All data is fictional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_source_selection_ui import _dataset, _free, _hold, _open
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.cards.staging import Staging
from aep_bi.host.bi_cards_api import route

TECH_CSV = "技術,領域,成熟度,新增測試需求\nEtherCAT,robotics,mature,週期抖動\n"
DELETE = "/api/bi/sources/delete"


def _ok(answer: Any) -> dict[str, Any]:
    status, payload = answer
    assert status == 200, payload
    return dict(payload)


def _cite(workspace: Path, dataset: str, source_id: str) -> None:
    """A committed Ingest run: the card EtherCAT cites the source as evidence."""
    body = {"dataset": dataset, "kind": "ingest", "source_id": source_id}
    run = _ok(route(workspace, "t", "POST", "/api/bi/runs", {}, body))["run"]
    detail = _ok(
        route(workspace, "t", "GET", f"/api/bi/runs/{run['id']}", {"dataset": dataset}, None)
    )
    for candidate in detail["candidates"]:
        path = f"/api/bi/runs/{run['id']}/candidates/{candidate['id']}"
        _ok(route(workspace, "t", "POST", path, {}, {"dataset": dataset, "review": "accepted"}))
    _ok(route(workspace, "t", "POST", f"/api/bi/runs/{run['id']}/commit", {}, {"dataset": dataset}))


def _row_button(page: BiPage, name: str, label: str) -> None:
    page.run(
        "[...document.querySelectorAll('#bi-b-sources tbody tr')]"
        f".find((r) => r.textContent.includes({json.dumps(name)}))"
        f".querySelectorAll('button').forEach((b) => {{ if (b.textContent === {json.dumps(label)})"
        " b.click(); })"
    )


def _rows(page: BiPage) -> list[str]:
    return list(
        page.run(
            "[...document.querySelectorAll('#bi-b-sources tbody tr')]"
            ".map((r) => r.dataset.source ? r.cells[1].textContent : '')"
        )
    )


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_deleting_chosen_and_single_sources_in_step_one(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    _dataset(workspace, "lab")
    staging = Staging(workspace, "lab")
    cited = staging.add_source("tech.csv", text=TECH_CSV, actor="alice")
    _cite(workspace, "lab", cited["id"])
    staging.add_source("wrong-1.md", text="# 放錯一\n", actor="alice")
    staging.add_source("wrong-2.md", text="# 放錯二\n", actor="alice")
    staging.add_source("wrong-3.md", text="# 放錯三\n", actor="alice")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, "lab")
            page.wait(page.shows("bi-b-sources", "wrong-3.md"))
            assert page.run("document.getElementById('bi-b-src-del').disabled")
            for name in ("wrong-1.md", "wrong-2.md", "tech.csv"):
                page.choose_row_source(name)
            # The Markdown pane shows a source about to go.
            page.run("biPickSource(bi.build.sources.find((s) => s.name === 'wrong-1.md')); 0")
            page.wait(page.shows("bi-b-md-h", "wrong-1.md"))
            page.see("bi-b-src-count", "顯示 4／4 份・已選 3 份")
            assert page.text_of("bi-b-src-del") == "刪除已選（3 份）"

            # One question beside the button; 取消 asks nothing more.
            page.click("#bi-b-src-del")
            page.see(
                "bi-b-src-del-ask", "將刪除 3 份來源與它們的 Markdown；尚未 push 的刪除無法復原"
            )
            assert PUSHED_HINT not in page.text_of("bi-b-src-del-ask")  # nothing pushed
            page.click_text("#bi-b-src-del-ask", "取消")
            page.wait("document.getElementById('bi-b-src-del-ask').hidden")
            assert len(_rows(page)) == 4

            # The live line while the first request is held.
            page.click("#bi-b-src-del")
            _hold(page, DELETE)
            page.click_text("#bi-b-src-del-ask", "確定刪除")
            page.see("bi-b-src-del-ask", "刪除中 1/3：wrong-1.md・")
            assert (
                page.run("document.getElementById('bi-b-src-del-ask').getAttribute('aria-busy')")
                == "true"
            )
            assert page.run("document.getElementById('bi-b-src-del').disabled")
            _free(page)

            page.see("bi-b-src-del-status", "已刪除 2 份；1 份未刪除：")
            status = page.text_of("bi-b-src-del-status")
            assert "tech.csv：卡片 「EtherCAT」以它為證據" in status
            assert page.run("document.getElementById('bi-b-src-del-ask').hidden")
            page.wait("document.querySelectorAll('#bi-b-sources tbody tr').length === 2")
            assert sorted(_rows(page)) == ["tech.csv", "wrong-3.md"]
            page.see("bi-b-src-count", "顯示 2／2 份・已選 1 份")
            assert page.text_of("bi-b-src-del") == "刪除已選（1 份）"
            assert page.run("document.getElementById('bi-b-md').hidden")  # its source went

            # A row's own 刪除 asks in that row.
            _row_button(page, "wrong-3.md", "刪除")
            page.wait(
                "[...document.querySelectorAll('#bi-b-sources tbody tr')]"
                ".some((r) => r.textContent.includes('將刪除 1 份來源'))"
            )
            _row_button(page, "wrong-3.md", "確定刪除")
            page.see("bi-b-src-del-status", "已刪除 1 份。")
            page.wait("document.querySelectorAll('#bi-b-sources tbody tr').length === 1")
            assert _rows(page) == ["tech.csv"]
            assert {s["name"] for s in Staging(workspace, "lab").sources()} == {"tech.csv"}


PUSHED_HINT = (
    "已 push 的檔案仍留在共用資料夾的版本紀錄裡；要從共用資料夾完全移除，"
    "請按該列「共用資料夾」欄的「撤回」。"
)


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_deleting_a_pushed_vault_source_points_to_withdraw(tmp_path: Path) -> None:
    from test_bi_vault import _commit, _push
    from test_bi_vault_sources_ui import FOLDER, _open_build

    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "sharepoint"
    shared.mkdir()
    made = _ok(
        route(workspace, "alice", "POST", "/api/bi/vaults", {},
              {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
               "author": "alice"})
    )  # fmt: skip
    vault_id = str(made["vault"]["id"])
    dataset = f"vault-{vault_id}"
    Staging(workspace, dataset).add_source(
        "pushed.md", text="# 已放上去\n", folder=FOLDER, actor="alice"
    )
    _commit(workspace, vault_id, "加入來源")
    _push(workspace, vault_id)
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open_build(page, dataset)
            page.see("bi-b-sources", "已放上去")
            _row_button(page, "pushed.md", "刪除")
            page.wait(
                "[...document.querySelectorAll('#bi-b-sources tbody tr')]"
                f".some((r) => r.textContent.includes({json.dumps(PUSHED_HINT)}))"
            )
            row = page.run(
                "[...document.querySelectorAll('#bi-b-sources tbody tr')]"
                ".find((r) => r.textContent.includes('pushed.md')).textContent"
            )
            assert "會在下次 commit、push 時移除；版本紀錄保留舊版" in row
            _row_button(page, "pushed.md", "確定刪除")
            page.see("bi-b-src-del-status", "1 份會在下次 commit、push 時移除。")
            page.see("bi-b-src-del-status", PUSHED_HINT)
            page.see("bi-b-sources", "commit、push 後移除")
