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
        wait("document.getElementById('bi-cov-cell').textContent.includes('還沒有卡片')")
        assert "Cell Phone × Wireless & Comm." in text_of("bi-cov-cell")
        shoot("coverage")
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("coverage-phone")
        size(1366, 1000, False)

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
        wait("document.getElementById('bi-b-v-state').textContent.includes('已套用 1／1')")
        state = text_of("bi-b-v-state")
        assert "虛構範例" in state and str(shared) in state
        assert not run("document.getElementById('bi-b-v-sync').hidden")
        assert run("document.getElementById('bi-b-v-convert').hidden")
        assert hashlib.sha256(demo_db.read_bytes()).hexdigest() == before
        (folder,) = [p for p in shared.iterdir() if p.is_dir()]
        assert (folder / "vault.json").is_file()
        assert len(list((folder / "changes").rglob("*.json"))) == 1
        assert not list(folder.rglob("*.sqlite"))  # no database in the shared folder
        assert "共用：" in str(
            run("document.getElementById('bi-dataset').selectedOptions[0].textContent")
        )
        shoot("vault-converted")
        click("#bi-b-v-sync")
        wait("document.getElementById('bi-notice').textContent.includes('已同步')")

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
        wait("document.getElementById('bi-b-v-err').textContent.includes('vault.json')")
        size(390, 844, True)
        assert not run(
            "document.documentElement.scrollWidth > document.documentElement.clientWidth"
        )
        shoot("vault-join-error-phone")
    finally:
        browser.close()
