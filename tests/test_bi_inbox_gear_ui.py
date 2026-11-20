"""The working domain's Telegram 收集 in the Data input ⚙ (owner 2026-11-21: put the collection
time where it is easy to find). With a working domain the ⚙ shows its bot, 開啟, 收集時間 and
審核提醒 with 儲存; with 全部領域 one line says to pick a domain. The real Agent Web server in a
temporary workspace joined to a copy of the fixture vault (`test_bi_stage_gear_ui`). All data
is fictional.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_stage_gear_ui import _open, _setup
from test_bi_vault import _call, _ok
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from aep_bi.host.bi_page import BI_PANE_HTML


def test_the_block_sits_in_the_data_input_settings() -> None:
    settings = BI_PANE_HTML.split('id="bi-b-set-source"', 1)[1].split('id="bi-b-adv-source"')[0]
    assert 'id="bi-inbox-gear"' in settings
    # 管理 → Telegram 收集 stays the all-domains view.
    assert 'id="bi-inbox-open"' in BI_PANE_HTML and 'id="bi-inbox"' in BI_PANE_HTML


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_working_domains_collect_time_is_set_in_the_data_input_gear(
    served: Any,  # noqa: F811
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    server, workspace, _benches = _setup(served, tmp_path, monkeypatch)
    with BiPage(tmp_path / "browser", server.address) as page:
        folder = _open(page)
        page.gear("source")
        page.wait("document.querySelector('#bi-inbox-gear-row input[type=time]') !== null")
        assert page.run("document.getElementById('bi-inbox-gear').closest('.extra-panel') !== null")
        page.run(
            "(() => { const row = document.getElementById('bi-inbox-gear-row');"
            " const [collect] = row.querySelectorAll('input[type=time]');"
            " collect.value = '18:00';"
            " row.querySelector('input[type=checkbox]').checked = true;"
            " [...row.querySelectorAll('button')].find((b) => b.textContent === '儲存')"
            ".click(); })()"
        )
        page.see("bi-inbox-gear-row", "已儲存")
        domains = _ok(_call(workspace, "GET", "/api/bi/inbox"))["domains"]
        (mine,) = [d for d in domains if d["collect_at"] == "18:00"]
        assert mine["enabled"] is True
        assert page.run("bi.build.homes[0].folder") == folder
        # 全部領域: one line, no row.
        page.choose("bi-b-src-folder", "sources")
        page.see("bi-inbox-gear-status", "先在「工作領域」選一個領域")
        assert page.run("document.getElementById('bi-inbox-gear-row').children.length") == 0
