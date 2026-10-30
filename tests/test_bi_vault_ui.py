"""The 「知識庫」 panel of 「建立與匯入」 and the coverage matrix, in a real browser.

BI vaults V4/V5 pages (`docs/phases/BI_VAULT.md` §6.2, §7.1): the real Agent
Web server and routes in a temporary workspace, with a temporary folder
standing in for the SharePoint folder. The Dashboard shows the segment x
technology-area matrix (the owner's chart) and says when the schema has no
field to place cards with; a cell opens its summary. In step 1 the demo
dataset is converted into a vault (the original dataset is left as it was),
the vault's status and 「立即同步」 work, a new vault is created and chosen,
and joining a folder that is not a vault is refused inline. Screenshots in
`.scratch/bi-vault/`.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture

from capabilities.bi_cards.store import BiStore

SHOTS = Path(__file__).resolve().parents[1] / ".scratch" / "bi-vault"


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_vault_panel_and_coverage_in_a_browser(served: Any, tmp_path: Path) -> None:  # noqa: F811
    from integrations.browser import Browser, BrowserError

    web, server, _recorder, _ = served
    workspace = web.runtime.layout.workspace_root
    shared = tmp_path / "sharepoint"  # stands in for the synced SharePoint folder
    shared.mkdir()
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

    def set_value(element_id: str, value: str) -> None:
        run(f"document.getElementById('{element_id}').value = {json.dumps(value)}")

    def size(width: int, height: int, mobile: bool) -> None:
        browser.page().call(
            "Emulation.setDeviceMetricsOverride",
            width=width,
            height=height,
            deviceScaleFactor=1,
            mobile=mobile,
        )

    def shoot(name: str) -> None:
        time.sleep(0.25)
        browser.screenshot(shots / f"{name}.png")

    demo_db = workspace / "bi" / "demo" / "bi.sqlite"
    try:
        size(1366, 1000, False)
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        click("#nav-knowledge")
        click("#kn-tabs [data-kn=bi]")
        wait("document.getElementById('bi-status-bar').hidden")
        click("#bi-demo")
        wait("document.getElementById('bi-notice').textContent.includes('示範資料已載入')")

        # -- the coverage matrix on the Dashboard -----------------------------------------
        wait("document.querySelectorAll('#bi-cov-body td button').length === 55")
        assert "schema 沒有 segments、tech_areas" in text_of("bi-cov-body")
        assert "預設矩陣" in text_of("bi-cov-sub")
        head = text_of("bi-cov-body")
        for label in ("Wireless Devices & Chipsets", "Cell Phone（重點）", "OSAT", "EMC"):
            assert label in head, label
        click("#bi-cov-body td button")
        # One wait for both: the cell panel re-renders, so a second read can land on it empty.
        wait(
            "(() => { const t = document.getElementById('bi-cov-cell').textContent;"
            " return t.includes('還沒有卡片') && t.includes('Cell Phone × Wireless & Comm.'); })()"
        )
        shoot("coverage")
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("coverage-phone")
        size(1366, 1000, False)

        # -- per-domain configuration (BI vault V10) ------------------------------------------
        wait("document.getElementById('bi-dom-sub').textContent.includes('尚未設定')")
        click("#bi-dom summary")
        click("#bi-dom-sample")
        assert "aidc-computing" in str(run("document.getElementById('bi-dom-text').value"))
        click("#bi-dom-save")
        wait("document.getElementById('bi-notice').textContent.includes('領域設定已儲存')")
        wait("document.getElementById('bi-cov-sub').textContent.includes('領域設定的矩陣')")
        # Schema v4 has no `segments` field: said so, the configuration is kept.
        wait("document.getElementById('bi-dom-warn').textContent.includes('schema 沒有欄位')")
        assert "第 1 版" in text_of("bi-dom-sub")
        shoot("domains")

        # -- step 1: the demo dataset becomes a vault ----------------------------------------
        click("#bi-views [data-bi-view=build]")
        wait("document.getElementById('bi-b-v-state').textContent.includes('只在這台電腦')")
        assert run("document.getElementById('bi-b-ds').value") == "demo"
        assert run("document.getElementById('bi-b-v-sync').hidden")
        before = hashlib.sha256(demo_db.read_bytes()).hexdigest()
        click("#bi-b-v-convert")
        assert run("document.getElementById('bi-b-v-convert').getAttribute('aria-expanded')") == (
            "true"
        )
        assert run("document.getElementById('bi-b-v-title').parentElement.hidden")
        set_value("bi-b-v-path", str(shared))
        set_value("bi-b-v-purpose", "虛構範例：示範資料轉成共用知識庫")
        click("#bi-b-v-go")
        wait("document.getElementById('bi-notice').textContent.includes('已轉成共用知識庫')")
        wait("document.getElementById('bi-dataset').value.startsWith('vault-')")
        wait(
            "document.getElementById('bi-b-v-state').textContent.includes('還沒 push 的 commit 0')"
        )
        state = text_of("bi-b-v-state")
        assert "虛構範例" in state and str(shared) in state
        assert not run("document.getElementById('bi-b-v-sync').hidden")
        assert run("document.getElementById('bi-b-v-convert').hidden")
        assert hashlib.sha256(demo_db.read_bytes()).hexdigest() == before
        (folder,) = [p for p in shared.iterdir() if p.is_dir()]
        assert (folder / "repo.json").is_file()
        # The whole dataset travels as one import commit.
        assert len(list((folder / "commits").rglob("*.json"))) == 1
        assert not list(folder.rglob("*.sqlite"))  # no database in the shared folder
        assert "共用：" in str(
            run("document.getElementById('bi-dataset').selectedOptions[0].textContent")
        )
        shoot("vault-converted")
        click("#bi-b-v-sync")
        wait("document.getElementById('bi-notice').textContent.includes('已同步')")

        # -- the 「版本」 area (knowledge repositories R5) ---------------------------------
        wait("document.getElementById('bi-b-ver-history').textContent.includes('轉成知識庫')")
        assert "還沒有發佈過" in text_of("bi-b-ver-reads")
        assert run("document.getElementById('bi-b-ver-commit').disabled")
        dataset = str(run("document.getElementById('bi-dataset').value"))
        store = BiStore(workspace, dataset)
        card = store.card_rows()[0]
        store.set_field(card["id"], "notes", "虛構備註", base_version=card["version"], actor="t")
        click("#bi-b-v-sync")
        wait("document.getElementById('bi-b-ver-pending').textContent.includes('notes')")
        assert "虛構備註" in text_of("bi-b-ver-pending")
        click("#bi-b-ver-commit")
        wait("document.getElementById('bi-notice').textContent.includes('請先寫這次改動的目的')")
        set_value("bi-b-ver-purpose", "補上虛構備註")
        click("#bi-b-ver-commit")
        wait("document.getElementById('bi-notice').textContent.includes('已 commit')")
        wait("!document.getElementById('bi-b-ver-push').disabled")
        click("#bi-b-ver-push")
        wait("document.getElementById('bi-notice').textContent.includes('已 push 1 個 commit')")
        wait("document.getElementById('bi-b-ver-history').textContent.includes('補上虛構備註')")
        assert len(list((folder / "commits").rglob("*.json"))) == 2
        assert "補上虛構備註" in (folder / "REPO.md").read_text(encoding="utf-8")
        click("#bi-b-ver-history li .bi-actions button:nth-child(1)")
        wait("document.querySelector('#bi-b-ver-history li').textContent.includes('虛構備註')")
        run(
            "[...document.querySelectorAll('#bi-b-ver-history li:first-child button')]"
            ".find((b) => b.textContent === '加 tag').click()"
        )
        run("document.querySelector('#bi-b-ver-history .bi-ver-ask input').value = 'v1'")
        click("#bi-b-ver-history .bi-ver-ask button.go")
        wait("document.getElementById('bi-notice').textContent.includes('已建立 tag「v1」')")
        run("window.confirm = () => true")
        wait(
            "[...document.querySelectorAll('#bi-b-ver-history button')]"
            ".some((b) => b.textContent === '發佈 v1')"
        )
        run(
            "[...document.querySelectorAll('#bi-b-ver-history button')]"
            ".find((b) => b.textContent === '發佈 v1').click()"
        )
        wait("document.getElementById('bi-b-ver-reads').textContent.includes('發佈版本「v1」')")
        wait("document.getElementById('bi-b-ver-history').textContent.includes('發佈中')")
        shoot("vault-versions")
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("vault-versions-phone")
        size(1366, 1000, False)

        # -- a new, empty vault ---------------------------------------------------------------
        click("#bi-b-v-new")
        assert not run("document.getElementById('bi-b-v-title').parentElement.hidden")
        set_value("bi-b-v-path", "")
        click("#bi-b-v-go")
        wait("document.getElementById('bi-b-v-err').textContent.includes('請填資料夾路徑')")
        set_value("bi-b-v-path", str(shared))
        click("#bi-b-v-go")
        wait("document.getElementById('bi-b-v-err').textContent.includes('請填知識庫名稱')")
        set_value("bi-b-v-path", str(shared))
        set_value("bi-b-v-title", "Market Signals")
        set_value("bi-b-v-purpose", "虛構範例")
        click("#bi-b-v-go")
        wait("document.getElementById('bi-notice').textContent.includes('已建立共用知識庫')")
        wait("document.getElementById('bi-b-v-state').textContent.includes('Market Signals')")
        assert run("document.getElementById('bi-dataset').value").startswith("vault-market-signals")
        assert len([p for p in shared.iterdir() if p.is_dir()]) == 2

        # -- joining a folder that is not a vault ------------------------------------------
        click("#bi-b-v-join")
        set_value("bi-b-v-path", str(tmp_path))
        click("#bi-b-v-go")
        wait("document.getElementById('bi-b-v-err').textContent.includes('repo.json')")
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("vault-join-error-phone")
    finally:
        browser.close()
