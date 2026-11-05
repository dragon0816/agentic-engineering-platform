"""The commit list as a table, readable 套用到, and the page's words staying true.

Owner's rule: 「ui請以簡單為主，善用table，menu/comobox」. A real browser on fictional data.
Screenshots in `commit-list/` with `AEP_UI_SHOTS`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_card_page_import import _apply, _preview
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore, PlannedRow

AIDC = "applications/aidc/sources"
PAGE = "---\ntype: technology\nname: FAKE-1\n---\n\n## 說明\n虛構的內容。\n"


def _vault(tmp_path: Path, workspace: Path) -> tuple[str, str]:
    shared = tmp_path / "sharepoint"
    shared.mkdir()
    made = _ok(
        _call(workspace, "POST", "/api/bi/vaults",
              {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
               "author": "alice"})
    )  # fmt: skip
    return str(made["vault"]["dataset"]), str(made["vault"]["id"])


def _open(page: BiPage, dataset: str) -> None:
    page.click("#bi-views [data-bi-view=build]")
    page.run(
        f"window.__opened = false; bi.want = {json.dumps(dataset)};"
        " biLoad().then(() => { window.__opened = true; }); 0"
    )
    page.wait("window.__opened")


def _rows(page: BiPage) -> list[list[str]]:
    found = page.run(
        "JSON.stringify([...document.querySelectorAll('#bi-b-ver-pending table tbody tr')]"
        ".map(r => [...r.cells].map(c => c.textContent)))"
    )
    return list(json.loads(str(found)))


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_commit_list_is_a_table_with_no_json_and_no_empty_rows(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    dataset, vault_id = _vault(tmp_path, workspace)

    # A value, shown as old and new.
    store = BiStore(workspace, dataset)
    store.apply(
        [
            PlannedRow(
                row=1,
                entity_type="Technology",
                canonical_key="FAKE-2",
                name="FAKE-2",
                values={"name": "FAKE-2", "standard_body": "IEEE"},
                synthetic=False,
            )
        ],
        filename="seed.csv",
        entity_type="Technology",
        actor="alice",
    )
    found = store.find("Technology", "FAKE-2")
    assert found is not None
    store.set_field(
        str(found["id"]), "standard_body", "IETF", base_version=int(found["version"]), actor="a"
    )
    # A source and a skill, which printed as JSON.
    Staging(workspace, dataset).add_source("筆記.md", text="# 筆記\n", actor="alice", folder=AIDC)
    rule = {"name": "aidc-extract", "role": "extract", "body": "虛構規則。",
            "applies_to": [AIDC, "library/skill-review/sources"]}  # fmt: skip
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/skills", rule))
    # A question added and deleted before any commit: nothing has changed.
    question = {"question": "虛構題？", "must": ["好"], "slug": "gone", "home": "aidc"}
    added = _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/checks", question))
    unit = next(q["unit"] for q in added["questions"] if q["question"] == question["question"])
    checks = f"/api/bi/vaults/{vault_id}/checks"
    _ok(_call(workspace, "POST", checks, {"delete": unit}))

    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "commit-list" if shots else None
        ) as page:
            _open(page, dataset)
            page.wait("document.querySelectorAll('#bi-b-ver-pending table').length === 1")
            heads = page.run(
                "[...document.querySelectorAll('#bi-b-ver-pending table thead th')]"
                ".map(h => h.textContent).join()"
            )
            assert heads == "名稱,種類,領域,改動"
            rows = _rows(page)
            assert rows, "the list is empty"
            shown = page.text_of("bi-b-ver-pending")

            # No JSON, and no row for what came to nothing.
            assert "{" not in shown and '"' not in shown and "[" not in shown
            assert "（沒有）" not in shown
            assert "虛構題" not in shown

            by_name = {row[0]: row for row in rows}
            source = next(r for name, r in by_name.items() if "筆記.md" in name)
            assert source[1] == "來源" and source[3] == "新增"
            skill = next(r for name, r in by_name.items() if "aidc-extract" in name)
            assert skill[1] == "判讀規則" and skill[3] == "新增"
            value = next(r for name, r in by_name.items() if "standard_body" in name)
            assert value[1] == "欄位" and "IEEE" in value[3] and "IETF" in value[3]

            # The count per domain stays, and the warning with one domain chosen.
            assert page.run(
                "document.getElementById('bi-b-ver-pending').textContent.includes('項')"
            )
            page.click("#bi-stepper [data-stage=test]")
            page.run("document.getElementById('bi-b-ver-pending').scrollIntoView(); 0")
            page.shoot("commit-list")

            # 改動 of a removed thing reads as words too.
            assert (
                page.run(
                    "biVerChange({unit: 'source:x', before: {name: 'a', size: 1}, after: null})"
                )
                == "移除"
            )
            assert (
                page.run("biVerChange({unit: 'evidence:c:f', before: [{}], after: [{}, {}]})")
                == "1 → 2 筆"
            )
            assert (
                page.run(
                    "biVerChange({unit: 'field:c:f', before: {value: ['a']}, after: {value: ['a', 'b']}})"
                )
                == "a → a、b"
            )

            # -- 套用到: names people know, the value itself kept --------------------------------
            page.wait(
                "document.getElementById('bi-b-sk-list').textContent.includes('aidc-extract')"
            )
            cell = (
                "[...document.querySelectorAll('#bi-b-sk-list tbody tr')]"
                ".find(r => r.textContent.includes('aidc-extract')).cells[3]"
            )
            assert "/" not in str(page.run(f"{cell}.textContent"))
            assert "skill-review" in str(page.run(f"{cell}.textContent"))
            title = str(page.run(f"{cell}.querySelector('[title]').title"))
            assert title.startswith("applications/") or title.startswith("library/")
            skills = _ok(_call(workspace, "GET", f"/api/bi/vaults/{vault_id}/skills"))["skills"]
            kept = next(s for s in skills if s["name"] == "aidc-extract")
            assert kept["applies_to"] == rule["applies_to"]


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_green_notice_goes_with_the_next_action_and_a_red_one_stays(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    dataset, _ = _vault(tmp_path, workspace)
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, dataset)
            page.run("biNotice(true, '虛構的成功'); 0")
            page.click("#bi-stepper [data-stage=ingest]")
            assert page.text_of("bi-notice") == ""

            page.run("biNotice(true, '虛構的成功'); 0")
            page.click("#bi-views [data-bi-view=cards]")
            assert page.text_of("bi-notice") == ""
            page.click("#bi-views [data-bi-view=build]")

            # Set by the press itself, it shows: what the action says is not cleared by it.
            page.run(
                "document.getElementById('bi-b-v-sync').addEventListener('click',"
                " () => biNotice(true, '這次的結果'), {once: true}); 0"
            )
            page.run("biNotice(true, '虛構的成功'); 0")
            page.click("#bi-b-v-sync")
            assert page.text_of("bi-notice") != "虛構的成功"

            # A failure stays until it is replaced: it may be the only word on what went wrong.
            page.run("biNotice(false, '虛構的失敗'); 0")
            page.click("#bi-stepper [data-stage=ingest]")
            assert page.text_of("bi-notice") == "虛構的失敗"


def _bar(page: BiPage) -> str:
    return page.text_of("bi-counts")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_file_converted_with_no_cards_yet_says_so(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    _ok(_call(workspace, "POST", "/api/bi/datasets", {"name": "empty", "schema": "bi.schema/v1.1"}))
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, "empty")
            assert "0" in _bar(page) and "還沒有資料" in _bar(page)
            page.upload("筆記.md", "# 筆記\n\n虛構。\n", "text/markdown")
            page.wait(page.shows("bi-counts", "還沒有卡片"))
            assert "1 份來源" in _bar(page)
            assert "尚未載入資料" not in _bar(page) and "還沒有資料" not in _bar(page)


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_dataset_converted_to_a_vault_shows_its_cards_at_once(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "sharepoint"
    shared.mkdir()
    _ok(_call(workspace, "POST", "/api/bi/datasets", {"name": "lab", "schema": "bi.schema/v1.1"}))
    plan: dict[str, Any] = _preview(workspace, "lab", [{"path": "BI/p.md", "text": PAGE}])
    _apply(workspace, plan["preview_id"])
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            _open(page, "lab")
            assert _bar(page).startswith("1")
            page.click("#bi-b-v-convert")
            page.set_value("bi-b-v-path", str(shared))
            page.set_value("bi-b-v-purpose", "虛構")
            page.set_value("bi-b-v-author", "alice")
            page.click("#bi-b-v-go")
            page.wait("document.getElementById('bi-dataset').value.startsWith('vault-')")
            assert _bar(page).startswith("1"), _bar(page)
            page.wait("document.getElementById('bi-status-build').hidden")
            assert _bar(page).startswith("1"), _bar(page)
            assert "更新於" in _bar(page)
