"""Step 1's converted Markdown as a preview, and the row that adds a file (owner, 2026-11-05:
「查看轉成MD的部份，我想要有預覽的功能」, 「轉檔的button位置和大小看的很不協調」).

The preview is the default and draws tables as tables; a source's own HTML and images stay
words, so nothing in a source runs or fetches anything. A real browser on fictional data.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from bi_page_driver import BiPage, browser_missing
from test_vault_asking_e2e import _bi_host, _Model, _served

from aep_bi.cards.store import BiStore

# 虛構範例: fictional.
SOURCE = """---
title: 虛構的市場筆記
owner: Alice
tags: 網通, 量測
---
# 需求

| 客戶 | 需求 |
|---|---|
| 虛構 A | TSN |
| 虛構 B | 800G |

<script>window.__ran = true</script>

<img src="http://203.0.113.9/x.png" onerror="window.__ran = true">

![圖](http://203.0.113.9/y.png)

[連到別處](javascript:window.__ran=true)
"""


def _mode(page: BiPage, value: str) -> None:
    """One button switches between the preview and the editor (owner 2026-11-19, C2)."""
    if page.run("document.getElementById('bi-b-md-mode').dataset.mode") != value:
        page.click("#bi-b-md-mode")
    assert page.run("document.getElementById('bi-b-md-mode').dataset.mode") == value
    assert page.text_of("bi-b-md-mode") == ("預覽" if value == "edit" else "編輯")


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_markdown_opens_as_a_preview_with_real_tables_and_nothing_runs(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    BiStore(layout.workspace_root, "demo").create("bi.schema/v1.1")
    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "md-preview" if shots else None
        ) as page:
            page.click("#bi-views [data-bi-view=build]")
            page.wait("document.getElementById('bi-status-build').hidden")

            # -- the row: one height, one baseline, and no browser wording ----------------
            rects = json.loads(
                str(
                    page.run(
                        "JSON.stringify(['#bi-b-class', '.bi-file', '#bi-b-upload'].map((s) => {"
                        " const r = document.querySelector(s).getBoundingClientRect();"
                        " return [r.top, r.bottom]; }))"
                    )
                )
            )
            assert len({round(top) for top, _ in rects}) == 1, rects
            assert len({round(bottom) for _, bottom in rects}) == 1, rects
            assert page.text_of("bi-b-file-name") == "還沒有選檔"
            assert page.run("document.getElementById('bi-b-file').offsetWidth <= 1")
            page.shoot("row-empty")

            page.upload("note.md", SOURCE, "text/markdown")
            page.wait("!document.getElementById('bi-b-md').hidden")
            page.wait("!document.getElementById('bi-b-md-view').hidden")
            assert page.run("document.getElementById('bi-b-md-mode').dataset.mode") == "view"
            assert page.run("document.getElementById('bi-b-md-edit').hidden")

            # -- a table is a table, the frontmatter a tidy one ---------------------------
            page.wait("document.querySelectorAll('#bi-b-md-view table').length === 2")
            front = page.text_of("bi-b-md-view")
            assert page.run(
                "document.querySelector('#bi-b-md-view .bi-md-front th').textContent"
            ) == ("title")
            assert "虛構的市場筆記" in front and "---" not in front
            assert (
                page.run(
                    "[...document.querySelectorAll('#bi-b-md-view table:not(.bi-md-front) th')]"
                    ".map((c) => c.textContent).join('/')"
                )
                == "客戶/需求"
            )
            assert page.run(
                "document.querySelectorAll('#bi-b-md-view table:not(.bi-md-front) tbody tr')"
                ".length === 2"
            )
            page.shoot("preview")

            # -- what a source says only shows ------------------------------------------
            assert page.run(
                "document.querySelectorAll('#bi-b-md-view script, #bi-b-md-view img,"
                " #bi-b-md-view iframe, #bi-b-md-view [onerror]').length === 0"
            )
            assert "<script>" in front and "onerror" in front
            assert not page.run("window.__ran === true")
            assert not page.run("document.querySelector('#bi-b-md-view a[href^=javascript]')")
            remote = page.run(
                "performance.getEntriesByType('resource')"
                ".filter((e) => e.name.includes('203.0.113.9')).length"
            )
            assert remote == 0

            # -- switching to edit, and back: the preview shows what was typed ------------
            _mode(page, "edit")
            assert not page.run("document.getElementById('bi-b-md-edit').hidden")
            assert page.run("document.getElementById('bi-b-md-view').hidden")
            assert str(page.run("document.getElementById('bi-b-md-text').value")).startswith("---")
            page.run(
                "document.getElementById('bi-b-md-text').value = '# 改過\\n\\n| a | b |\\n|---|---|"
                "\\n| 1 | 2 |\\n'"
            )
            page.shoot("edit")
            _mode(page, "view")
            page.see("bi-b-md-view", "改過")
            assert page.run("document.querySelectorAll('#bi-b-md-view table').length === 1")

            # -- saved, it opens on the preview again -------------------------------------
            _mode(page, "edit")
            page.click("#bi-b-md-save")
            page.wait("document.getElementById('bi-b-md-info').textContent.includes('人工修改')")
            page.wait("document.getElementById('bi-b-md-mode').dataset.mode === 'view'")
            page.see("bi-b-md-view", "改過")

            # -- the row after 轉檔: the chosen file is forgotten, in Chinese -------------
            assert page.text_of("bi-b-file-name") == "還沒有選檔"
            page.run(
                "(() => { const dt = new DataTransfer();"
                " dt.items.add(new File(['x'], 'a.md')); dt.items.add(new File(['y'], 'b.md'));"
                " const f = document.getElementById('bi-b-file'); f.files = dt.files;"
                " f.dispatchEvent(new Event('change')); })()"
            )
            assert page.text_of("bi-b-file-name") == "2 個檔案"
            assert not page.run("document.getElementById('bi-b-upload').disabled")

            # -- a phone: stacked, full width, nothing pushes the page sideways -----------
            page.browser.page().call(
                "Emulation.setDeviceMetricsOverride",
                width=390,
                height=844,
                deviceScaleFactor=1,
                mobile=True,
            )
            page.wait(
                "document.documentElement.scrollWidth <= document.documentElement.clientWidth"
            )
            page.shoot("phone")
