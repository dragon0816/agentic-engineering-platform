"""Commit and push are reachable whenever something waits, not only after a reading run.

Acceptance F12, 2026-11-06: 版本 (commit, push) showed only at the end of review. The status
line under the top row links to it from any tab. A real browser on fictional data.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_bi_vault import _call, _ok
from test_vault_asking_e2e import _bi_host, _Model, _served

from integrations.browser import Browser

QUIET = "window.__aepWatch.open.length === 0"
LINKS = "[...document.querySelectorAll('#bi-b-v-state button.bi-link')]"


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_status_line_opens_commit_and_push_from_any_tab(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The benchmark above the version form arrives after the share tables. Keep
    # this response ordering deterministic instead of relying on runner speed.
    original_navigate = Browser.navigate

    def navigate(browser: Browser, address: str) -> Any:
        browser.page().call(
            "Page.addScriptToEvaluateOnNewDocument",
            source=(
                "(() => { const real = window.fetch; let release;"
                " const gate = new Promise((go) => { release = go; });"
                " window.__releaseBench = release; window.__benchWaiting = false;"
                " window.fetch = async (u, o) => {"
                " if (String(u).includes('/checks') && (!o || !o.method || o.method === 'GET')) {"
                " window.__benchWaiting = true; await gate; } return real(u, o); }; })()"
            ),
        )
        return original_navigate(browser, address)

    monkeypatch.setattr(Browser, "navigate", navigate)
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
    # A change that is no card: a question, written outside any run.
    body = {"question": "虛構題？", "must": ["好"], "slug": "q1", "home": "aidc"}
    _ok(_call(workspace, "POST", f"/api/bi/vaults/{vault_id}/checks", body))

    shots = os.environ.get("AEP_UI_SHOTS")
    with _served(config, layout, _Model("none", {})) as server:
        with BiPage(
            tmp_path / "browser", server.address, Path(shots) / "version" if shots else None
        ) as page:
            page.choose("bi-dataset", dataset)
            page.click("#bi-views [data-bi-view=cards]")
            page.wait(f"{LINKS}.some((b) => b.textContent === '還沒 commit 的改動 1 個')", 60)
            # Nothing to push yet: that count stays plain text.
            assert "還沒 push 的 commit 0 個" in page.text_of("bi-b-v-state")
            assert page.run(f"{LINKS}.length") == 1
            page.shoot("link")

            page.run(f"{LINKS}[0].click()")
            page.wait("bi.view === 'build' && bi.build.stage === 'test'", 60)
            page.wait("!document.getElementById('bi-b-ver').hidden", 60)
            page.wait("window.__benchWaiting", 60)
            page.wait(QUIET, 60)  # every other table has been drawn
            page.run("window.__releaseBench()")
            page.wait(QUIET, 60)
            page.wait("document.getElementById('bi-b-bq-list').textContent.includes('虛構題')", 60)
            # 分享 opens as a tab of the side area (owner 2026-11-20), step 3 beside it, in
            # view and ready for the commit's purpose, even though step 3 was still loading.
            in_side = (
                "sideHas('bi-share') && document.getElementById('bi-b-ver')"
                ".closest('.extra-panel') === document.getElementById('extra-panel-bi-share')"
            )
            visible_version = (
                "(() => { const v = document.getElementById('bi-b-ver').getBoundingClientRect();"
                " return v.width > 0 && v.top >= 0 && v.top < innerHeight; })()"
            )
            page.wait(in_side, 60)
            page.wait(visible_version, 60)
            assert page.run("bi.view === 'build' && bi.build.stage === 'test'")
            assert page.run("document.activeElement.id") == "bi-b-ver-purpose"
            page.see("bi-b-ver-pending", "虛構題")
            page.shoot("version")

            page.set_value("bi-b-ver-purpose", "加一題")
            page.click("#bi-b-ver-commit")
            page.wait(f"{LINKS}.some((b) => b.textContent === '你還沒 push 的 commit 1 個')", 60)
            assert "還沒 commit 的改動 0 個" in page.text_of("bi-b-v-state")
