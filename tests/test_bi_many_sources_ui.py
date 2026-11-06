"""Step 1 with hundreds of sources, as market-intel has (owner, 2026-11-05: 「按"看/改"沒反應」).

The table keeps its own scroller, 看／改 opens the Markdown beside it in view, and a failed
load says so there. Also the 卡片 tab: a filter is always in sight. A real browser on
fictional data.
"""

from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards.staging import Staging
from capabilities.bi_cards.store import BiStore, PlannedRow

MANY = 900
AIDC = "applications/aidc/sources"
FAR = "來源-0880.md"


def _in_view(page: BiPage, selector: str) -> bool:
    return bool(
        page.run(
            f"(() => {{ const r = document.querySelector({json.dumps(selector)})"
            ".getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight"
            " && r.height > 0; })()"
        )
    )


def _top_rect(page: BiPage, selector: str) -> dict[str, float]:
    found = page.run(
        f"JSON.stringify(document.querySelector({json.dumps(selector)}).getBoundingClientRect())"
    )
    return dict(json.loads(str(found)))


def _press(page: BiPage, name: str) -> None:
    page.run(
        "(() => { const row = [...document.querySelectorAll('#bi-b-sources tbody tr')]"
        f".find((r) => r.textContent.includes({json.dumps(name)}));"
        " row.scrollIntoView({block: 'nearest'});"
        " [...row.querySelectorAll('button')].find((b) => b.textContent.includes('看／改'))"
        ".click(); })()"
    )


def _sources(workspace: Path, dataset: str, count: int, **given: Any) -> None:
    """Fast: one real source, its rows copied, so a list this long takes seconds to set up."""
    staging = Staging(workspace, dataset)
    first = staging.add_source("來源-0000.md", text="# 第一份\n\n內容。\n", actor="alice", **given)
    with sqlite3.connect(staging.path) as db:
        db.row_factory = sqlite3.Row
        row = dict(db.execute("SELECT * FROM sources WHERE id = ?", (first["id"],)).fetchone())
        marks = [dict(m) for m in db.execute(
            "SELECT * FROM markdown WHERE source_id = ?", (first["id"],))]  # fmt: skip
        for index in range(1, count):
            ident = f"copy{index:08d}"
            copied = {**row, "id": ident, "name": f"來源-{index:04d}.md",
                      "sha256": f"{index:064x}"}  # fmt: skip
            db.execute(
                f"INSERT INTO sources ({', '.join(copied)}) VALUES "
                f"({', '.join('?' * len(copied))})",
                tuple(copied.values()),
            )
            for mark in marks:
                moved = {**mark, "source_id": ident}
                db.execute(
                    f"INSERT INTO markdown ({', '.join(moved)}) VALUES "
                    f"({', '.join('?' * len(moved))})",
                    tuple(moved.values()),
                )
    db.close()


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_many_sources_stay_in_their_scroller_and_the_markdown_opens_beside_them(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    BiStore(workspace, "demo").create("bi.schema/v1.1")
    _sources(workspace, "demo", MANY)
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "many-sources" if shots else None
        ) as page:
            started = time.monotonic()
            page.wait(f"document.querySelectorAll('#bi-b-sources tbody tr').length === {MANY}")
            drawn = time.monotonic() - started
            print(f"\n{MANY} sources drawn in {drawn:.2f} s")
            drawing = page.run(
                "(() => { const t = performance.now(); biRenderSources();"
                " return performance.now() - t; })()"
            )
            print(f"one redraw of {MANY} rows: {float(drawing):.0f} ms")
            assert float(drawing) < 1000
            assert page.text_of("bi-b-src-count") == f"顯示 {MANY}／{MANY} 份・已選 0 份"

            # -- the table does not push the page ----------------------------------------
            split, scroller = _top_rect(page, "#bi-b-src-split"), _top_rect(page, "#bi-b-sources")
            assert split["height"] < 1000
            assert scroller["height"] > split["height"]  # it scrolls inside
            assert page.run("document.documentElement.scrollHeight < 3 * innerHeight"), (
                "900 rows must not make the page long"
            )

            # -- 看／改 far down the list: the Markdown is in view at once, beside it ----
            _press(page, FAR)
            page.wait("!document.getElementById('bi-b-md').hidden")
            page.see("bi-b-md-h", FAR)
            assert _in_view(page, "#bi-b-md-h"), "the pane is out of view"
            assert _in_view(page, "#bi-b-md-view")
            pane = _top_rect(page, "#bi-b-src-pane")
            assert pane["left"] > _top_rect(page, "#bi-b-sources")["left"]
            assert "第一份" in str(page.run("document.getElementById('bi-b-md-text').value"))
            page.shoot("opened")

            # -- a row opens it too; a press on the row's own radio as well ---------------
            page.run(
                "[...document.querySelectorAll('#bi-b-sources tbody tr')]"
                ".find((r) => r.textContent.includes('來源-0002.md')).cells[1].click()"
            )
            page.see("bi-b-md-h", "來源-0002.md")
            assert page.run(
                "document.querySelector('#bi-b-sources tbody tr[aria-selected=true]')"
                ".textContent.includes('來源-0002.md')"
            )

            # -- a failure shows in the pane, with a way to try again ----------------------
            page.run(
                "(() => { const real = window.fetch; window.__realFetch = real;"
                " window.fetch = (u, o) => String(u).includes('/markdown')"
                ' ? Promise.resolve(new Response(\'{"code":"boom","message":"讀不到"}\','
                " {status: 500})) : real(u, o); })()"
            )
            _press(page, "來源-0003.md")
            page.see("bi-b-md-status", "Markdown 沒有載入")
            assert page.run("document.getElementById('bi-b-md').hidden")
            assert _in_view(page, "#bi-b-md-status")
            assert "Markdown" not in page.text_of("bi-notice")
            page.shoot("failed")
            page.run("window.fetch = window.__realFetch")
            page.click_text("#bi-b-md-status", "重試")
            page.see("bi-b-md-h", "來源-0003.md")
            assert page.run("document.getElementById('bi-b-md-status').hidden")

            # -- the name search, with the count -------------------------------------------
            page.set_value("bi-b-src-q", "來源-012")
            page.run("document.getElementById('bi-b-src-q').dispatchEvent(new Event('input'))")
            page.wait("document.querySelectorAll('#bi-b-sources tbody tr').length === 10")
            assert page.text_of("bi-b-src-count").startswith(f"顯示 10／{MANY} 份・已選 ")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_in_a_vault_the_table_follows_the_domain_and_converting_opens_the_result(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    workspace = layout.workspace_root
    shared = tmp_path / "sharepoint"
    shared.mkdir()
    made: dict[str, Any] = _ok(
        _call(workspace, "POST", "/api/bi/vaults",
              {"path": str(shared), "title": "Market", "schema": "bi.schema/v1.1",
               "author": "alice"})
    )  # fmt: skip
    dataset = str(made["vault"]["dataset"])
    staging = Staging(workspace, dataset)
    staging.add_source("aidc.md", text="# AIDC\n", actor="alice", folder=AIDC)
    staging.add_source("root.md", text="# 根\n", actor="alice", folder="sources")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.run(
                "(() => { const s = document.getElementById('bi-dataset');"
                f" s.value = {json.dumps(dataset)}; s.dispatchEvent(new Event('change')); }})()"
            )
            page.wait("document.querySelectorAll('#bi-b-sources tbody tr').length === 2")
            page.wait(
                f"[...document.getElementById('bi-b-src-folder').options]"
                f".some((o) => o.value === {json.dumps(AIDC)})"
            )
            page.run(
                "(() => { const s = document.getElementById('bi-b-src-folder');"
                f" s.value = {json.dumps(AIDC)}; s.dispatchEvent(new Event('change')); }})()"
            )
            page.wait("document.querySelectorAll('#bi-b-sources tbody tr').length === 1")
            assert "aidc.md" in page.text_of("bi-b-sources")
            assert page.text_of("bi-b-src-count") == "顯示 1／2 份・已選 0 份"

            # After 轉檔 the new source is selected and its Markdown opens.
            page.upload("new.md", "# 新來源\n\n轉檔後的內容。\n", "text/markdown")
            page.see("bi-b-md-h", "new.md")
            assert "轉檔後的內容" in str(page.run("document.getElementById('bi-b-md-text').value"))
            assert _in_view(page, "#bi-b-md-h")
            assert page.run(
                "document.querySelector('#bi-b-sources tbody tr[aria-selected=true]')"
                ".textContent.includes('new.md')"
            )


def _row(kind: str, name: str, **values: Any) -> PlannedRow:
    return PlannedRow(
        row=1,
        entity_type=kind,
        canonical_key=name,
        name=name,
        values={"name": name, **values},
        synthetic=False,
    )


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_card_tab_shows_every_domain_and_names_the_filter_it_holds(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    store = BiStore(layout.workspace_root, "demo")
    store.create("bi.schema/v1.1")
    store.apply(
        [
            _row("Technology", "機器人技術", domain=["robotics"]),
            _row("Technology", "AIDC 技術", domain=["AIDC"]),
            _row("Technology", "航太技術", domain=["aerospace"]),
            _row("Signal", "AIDC 訊號", domain="AIDC", title="AIDC 訊號", date="2026-11-01"),
        ],
        filename="t.csv",
        entity_type="Technology",
        actor="alice",
    )
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(tmp_path / "browser", server.address) as page:
            page.click("#bi-views [data-bi-view=cards]")
            # All of them, with nothing chosen: the filter's own default shows every domain.
            page.wait("document.querySelectorAll('#bi-cards .bi-card-row').length === 4")
            assert page.run("document.getElementById('bi-card-domain').value") == ""
            assert page.text_of("bi-card-count") == "4 張卡片"
            options = json.loads(
                str(
                    page.run(
                        "JSON.stringify([...document.getElementById('bi-card-domain').options]"
                        ".map(o => o.value))"
                    )
                )
            )
            assert options[0] == "" and {"aidc", "robotics", "aerospace", "wireless"} <= set(
                options
            )

            def choose(element: str, value: str) -> None:
                page.run(
                    f"(() => {{ const s = document.getElementById({json.dumps(element)});"
                    f" s.value = {json.dumps(value)}; s.dispatchEvent(new Event('change')); }})()"
                )

            # The data's casing does not matter: the page's `aidc` finds `AIDC` cards.
            choose("bi-card-domain", "aidc")
            page.wait("document.querySelectorAll('#bi-cards .bi-card-row').length === 2")
            assert page.text_of("bi-card-count") == "2 張卡片（共 4 張）"

            # A type with none in the domain says which filter did it.
            choose("bi-card-domain", "robotics")
            page.wait("document.querySelectorAll('#bi-cards .bi-card-row').length === 1")
            choose("bi-type", "Signal")
            page.wait("document.getElementById('bi-cards').textContent.includes('沒有這類卡片')")
            assert "Robotics" in page.text_of("bi-cards")
            assert page.text_of("bi-card-count") == "0 張卡片（共 4 張）"
    shutil.rmtree(tmp_path / "browser", ignore_errors=True)
