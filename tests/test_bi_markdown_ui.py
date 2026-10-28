"""Source Markdown and full-text search in the BI area, in a real browser.

BI vaults V2/V3 pages (`docs/phases/BI_VAULT.md` §5, §6.1): the real Agent
Web server and routes in a temporary workspace. A CSV source shows its format
and Markdown revision; 「看／改」 opens the converted table, an edit is saved as
revision 2 (an older revision is read only), a save made from a revision
someone else replaced is refused with the newer revision named, a trial run
reads the edited Markdown, and the cards view searches card values and
source passages with the index state shown. Screenshots in `.scratch/bi-md/`.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "bi-md"
# 虛構範例: fictional rows.
TECH_CSV = "技術,領域,成熟度\nEtherCAT,robotics,mature\nTSN,robotics,growth\n"


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_source_markdown_and_search_in_a_browser(served: Any, tmp_path: Path) -> None:  # noqa: F811
    from integrations.browser import Browser, BrowserError

    web, server, _recorder, _ = served
    shots = Path(os.environ.get("AEP_UI_SHOTS") or SHOTS)
    shots.mkdir(parents=True, exist_ok=True)
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def run(expression: str) -> Any:
        return browser._evaluate(expression)

    def wait(expression: str, seconds: float = 60) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = run(expression)
            except BrowserError:
                value = None
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(expression)

    def click(selector: str) -> None:
        run(f"document.querySelector({json.dumps(selector)}).click()")

    def text_of(element_id: str) -> str:
        return str(run(f"document.getElementById('{element_id}').textContent"))

    def shoot(name: str) -> None:
        time.sleep(0.25)
        browser.screenshot(shots / f"{name}.png")

    try:
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=1366,
            height=1000,
            deviceScaleFactor=1,
            mobile=False,
        )
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        click("#nav-knowledge")
        click("#kn-tabs [data-kn=bi]")
        wait("document.getElementById('bi-status-bar').hidden")
        click("#bi-views [data-bi-view=build]")
        wait("document.getElementById('bi-status-build').hidden")
        run(
            "(() => { const dt = new DataTransfer();"
            f" dt.items.add(new File([{json.dumps(TECH_CSV)}], 'tech.csv', {{type: 'text/csv'}}));"
            " const f = document.getElementById('bi-b-file'); f.files = dt.files;"
            " f.dispatchEvent(new Event('change')); })()"
        )
        click("#bi-b-upload")
        wait("document.querySelectorAll('#bi-b-sources tbody input:checked').length === 1")
        row = text_of("bi-b-sources")
        assert "表格（預設表格規則）" in row and "第 1 版" in row

        # -- the converted Markdown, edited into revision 2 ---------------------------------
        run(
            "[...document.querySelectorAll('#bi-b-sources button')]"
            ".find(b => b.textContent.includes('看／改')).click()"
        )
        wait("!document.getElementById('bi-b-md').hidden")
        table = str(run("document.getElementById('bi-b-md-text').value"))
        assert table.startswith("| 技術 | 領域 | 成熟度 |") and "| TSN |" in table
        assert "轉檔" in text_of("bi-b-md-info")
        run(
            "{ const box = document.getElementById('bi-b-md-text');"
            " box.value = box.value.replace('| TSN |', '| TSN-2026 |'); }"
        )
        run("document.getElementById('bi-b-md-note').value = '更新技術名稱'")
        click("#bi-b-md-save")
        wait("document.getElementById('bi-notice').textContent.includes('已存成第 2 版')")
        wait("document.getElementById('bi-b-sources').textContent.includes('第 2 版')")
        wait("document.getElementById('bi-b-md-info').textContent.includes('人工修改')")
        shoot("markdown-rev2")
        run(
            "{ const s = document.getElementById('bi-b-md-rev'); s.value = '1';"
            " s.dispatchEvent(new Event('change')); }"
        )
        wait("document.getElementById('bi-b-md-save').disabled")
        assert "舊版次" in text_of("bi-b-md-msg")
        run(
            "{ const s = document.getElementById('bi-b-md-rev'); s.value = '2';"
            " s.dispatchEvent(new Event('change')); }"
        )
        wait("!document.getElementById('bi-b-md-save').disabled")

        # -- someone else saves first: this save is refused ----------------------------------
        source_id = run("document.querySelector('#bi-b-sources tbody input:checked').value")
        run(
            f"biCall('/api/bi/sources/' + {json.dumps(source_id)} + '/markdown',"
            " {dataset: 'demo', markdown: document.getElementById('bi-b-md-text').value"
            " + '\\n', base_rev: 2, note: '別人'}).then(() => window.__other = true)"
        )
        wait("window.__other === true")
        run("document.getElementById('bi-b-md-text').value += '\\n<!-- mine -->'")
        click("#bi-b-md-save")
        wait("document.getElementById('bi-b-md-msg').textContent.includes('第 3 版')")
        assert "你的修改沒有存" in text_of("bi-b-md-msg")
        run(
            "[...document.querySelectorAll('#bi-b-md-msg button')]"
            ".find(b => b.textContent.includes('重新載入')).click()"
        )
        wait(
            "document.getElementById('bi-b-md-info').textContent"
            ".includes('第 3 版（目前是第 3 版）')"
        )

        # -- the trial reads the edited Markdown --------------------------------------------
        click("#bi-stepper [data-stage=method]")
        wait("!document.querySelector('#bi-view-build .kp-stage[data-stage=method]').hidden")
        assert run("document.getElementById('bi-b-m-pick').value") == "builtin:rules"
        click("#bi-b-trial")
        wait("document.getElementById('bi-b-trial-result').textContent.includes('試跑完成')")
        assert "TSN-2026" in text_of("bi-b-trial-result")

        # -- full-text search over the source passages ----------------------------------------
        click("#bi-views [data-bi-view=cards]")
        run("document.getElementById('bi-fts').open = true")
        wait("document.getElementById('bi-fts-index').textContent.includes('索引')")
        run("document.getElementById('bi-fts-q').value = 'TSN-2026'")
        click("#bi-fts-go")
        wait("document.getElementById('bi-fts-out').textContent.includes('來源原文（1）')")
        found = text_of("bi-fts-out")
        assert "tech.csv" in found and "第 3 版" in found and "卡片（0）" in found
        assert run("document.querySelector('#bi-fts-out mark').textContent") == "TSN-2026"
        shoot("search")
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=390,
            height=844,
            deviceScaleFactor=1,
            mobile=True,
        )
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("search-phone")
    finally:
        browser.close()
