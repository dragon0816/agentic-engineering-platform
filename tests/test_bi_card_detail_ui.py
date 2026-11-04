"""The card tab: the card scrolls beside the list at its height, and says first what it
is about (owner, 2026-11-05). In a real browser, on fictional cards."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_vault_asking_e2e import _bi_host, _Model, _served

from capabilities.bi_cards.store import BiStore, PlannedRow

LONG = "很長的備註。" * 400


def _row(name: str, **values: Any) -> PlannedRow:
    return PlannedRow(
        row=1,
        entity_type="Technology",
        canonical_key=name,
        name=name,
        values={"name": name, **values},
        synthetic=False,
    )


def _rect(page: BiPage, selector: str) -> dict[str, float]:
    found = page.run(
        f"JSON.stringify(document.querySelector({json.dumps(selector)}).getBoundingClientRect())"
    )
    return dict(json.loads(str(found)))


def _open(page: BiPage, name: str) -> None:
    page.run(
        "[...document.querySelectorAll('#bi-cards .bi-card-row')]"
        f".find((b) => b.textContent.includes({json.dumps(name)})).click()"
    )
    page.wait(
        "(document.getElementById('bi-detail-title') || {}).textContent === " + json.dumps(name)
    )


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_card_scrolls_beside_the_list_and_opens_with_its_abstract(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    store = BiStore(layout.workspace_root, "demo")
    store.create("bi.schema/v1.1")
    store.apply(
        [
            _row(
                "有摘要",
                summary="虛構的摘要內容",
                usage="虛構的用途",
                scope="虛構的範圍",
                notes=LONG,
            ),
            _row("沒摘要", notes=LONG),
            *[_row(f"技術 {index:02d}") for index in range(40)],
        ],
        filename="t.csv",
        entity_type="Technology",
        actor="alice",
    )
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "card-detail" if shots else None
        ) as page:
            page.click("#bi-views [data-bi-view=cards]")
            page.wait("document.querySelectorAll('#bi-cards .bi-card-row').length === 42")
            _open(page, "有摘要")

            # -- one height, tops and bottoms in line, each scrolling on its own ----------
            left, right = _rect(page, "#bi-card-list"), _rect(page, "#bi-detail")
            assert abs(left["top"] - right["top"]) < 1
            assert abs(left["bottom"] - right["bottom"]) < 1
            count, cards = _rect(page, "#bi-card-count"), _rect(page, "#bi-cards")
            assert abs(count["top"] - right["top"]) < 20  # the count line starts the column
            assert abs(cards["bottom"] - right["bottom"]) < 1
            pane = "document.getElementById('bi-detail')"
            assert page.run(f"{pane}.scrollHeight > {pane}.clientHeight")
            assert page.run(
                "(() => { const l = document.getElementById('bi-cards');"
                " return l.scrollHeight > l.clientHeight; })()"
            )

            # Scrolling the card moves neither the list nor the page.
            before = _rect(page, "#bi-cards")["top"]
            page.run(f"{pane}.scrollTop = 500")
            page.wait(f"{pane}.scrollTop >= 500")
            assert _rect(page, "#bi-cards")["top"] == before

            # -- the abstract comes first, in order, and only there ------------------------
            order = json.loads(
                str(
                    page.run(
                        "JSON.stringify([...document.querySelectorAll("
                        "'#bi-detail-abstract .bi-field')].map(r => r.dataset.field))"
                    )
                )
            )
            assert order == ["summary", "usage", "scope"]
            shown = page.text_of("bi-detail-abstract")
            for word in ("摘要", "虛構的摘要內容", "用途", "範圍", "提更正單"):
                assert word in shown, word
            assert "沒有摘要" not in shown
            assert page.run(
                "(() => { const h = [...document.querySelectorAll('#bi-detail-body h4')]"
                ".find(x => x.textContent === '欄位');"
                " const a = document.getElementById('bi-detail-abstract');"
                " return Boolean(a.compareDocumentPosition(h)"
                " & Node.DOCUMENT_POSITION_FOLLOWING); })()"
            )
            assert (
                page.run("document.querySelectorAll('#bi-detail-body [data-field=summary]').length")
                == 1
            )
            page.run(f"{pane}.scrollTop = 0")
            page.shoot("with-abstract")

            # -- another card opens at its top, and says it has none -----------------------
            page.run(f"{pane}.scrollTop = 500")
            page.wait(f"{pane}.scrollTop >= 500")
            _open(page, "沒摘要")
            assert page.run(f"{pane}.scrollTop") == 0
            assert page.text_of("bi-detail-abstract").strip() == "沒有摘要"
            page.shoot("no-abstract")

            # -- a phone: stacked, and the page scrolls ------------------------------------
            page.browser.page().call(
                "Emulation.setDeviceMetricsOverride",
                width=390,
                height=800,
                deviceScaleFactor=1,
                mobile=True,
            )
            page.wait("document.documentElement.clientWidth <= 400")
            left, right = _rect(page, "#bi-card-list"), _rect(page, "#bi-detail")
            assert right["top"] >= left["bottom"]
            assert page.run(f"getComputedStyle({pane}).overflowY") == "visible"
            assert not page.run(
                "document.documentElement.scrollWidth > document.documentElement.clientWidth"
            )
            page.shoot("phone")
