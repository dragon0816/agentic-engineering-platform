"""The create-vault form sets the vault's id (R6: `market-intel`, with no random ending).

A real browser on the real Agent Web page, a temporary folder. All data is fictional.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pytest
from test_bi_vault_ui import _browser_missing
from test_draft_install_cards import served  # noqa: F401 - the real Agent Web fixture


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_a_person_can_name_the_vault_id(served: Any, tmp_path: Path) -> None:  # noqa: F811
    from integrations.browser import Browser, BrowserError

    _, server, _, _ = served
    shared = tmp_path / "shared"
    shared.mkdir()
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def wait(expression: str, seconds: float = 60) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                value = browser._evaluate(expression)
            except BrowserError:
                value = None
            if value:
                return value
            time.sleep(0.1)
        raise AssertionError(expression)

    def click(selector: str) -> None:
        browser._evaluate(f"document.querySelector({json.dumps(selector)}).click()")

    def put(element_id: str, value: str) -> None:
        browser._evaluate(f"document.getElementById('{element_id}').value = {json.dumps(value)}")

    try:
        browser.navigate(server.address)
        wait('!document.getElementById("send").disabled')
        click("#nav-knowledge")
        click("#kn-tabs [data-kn=bi]")
        wait("document.getElementById('bi-status-bar').hidden")
        click("#bi-views [data-bi-view=build]")
        click("#bi-stepper [data-stage=source]")
        click("#bi-b-v-new")
        wait("!document.getElementById('bi-b-v-form').hidden")
        assert not browser._evaluate("document.getElementById('bi-b-v-id').parentElement.hidden")
        put("bi-b-v-path", str(shared))
        put("bi-b-v-title", "Market Signals")
        put("bi-b-v-purpose", "虛構範例")

        # A bad id is said, and nothing is made.
        put("bi-b-v-id", "Not An Id")
        click("#bi-b-v-go")
        wait("document.getElementById('bi-b-v-err').textContent.includes('小寫英數字')")
        assert list(shared.iterdir()) == []

        # The id typed is the id, with no random ending.
        put("bi-b-v-id", "market-fiction")
        click("#bi-b-v-go")
        wait("document.getElementById('bi-dataset').value === 'vault-market-fiction'")
        wait("bi.vaultArrived === null")
        wait("document.getElementById('bi-notice').textContent.includes('已建立共用知識庫')")
        assert (shared / "market-fiction" / "repo.json").is_file()

        # In the other modes the field is not offered.
        click("#bi-b-v-join")
        wait("!document.getElementById('bi-b-v-form').hidden")
        assert browser._evaluate("document.getElementById('bi-b-v-id').parentElement.hidden")
    finally:
        browser.close()
