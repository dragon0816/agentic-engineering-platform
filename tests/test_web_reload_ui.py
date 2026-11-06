"""A reload (F5) keeps Agent Web open; nothing that reaches the address without the token gets in.

The page takes `?token=` out of the address at once, and the server let the page in only with
it, so a reload gave 「Open the address this command printed.」 The tab now keeps this run's
token in `sessionStorage`, which only this origin's scripts read and which goes with the tab.
The token still guards every request: another local user or a website gets a page with no
secret, and a token from an earlier run is refused once and not tried again.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from bi_page_driver import browser_missing
from test_vault_asking_e2e import _bi_host, _Model, _served

from integrations.browser import Browser

SEND_READY = '!!document.getElementById("send") && !document.getElementById("send").disabled'


def _get(url: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(url, timeout=10) as reply:  # noqa: S310 - loopback
            return reply.status, reply.read().decode("utf-8")
    except urllib.error.HTTPError as refused:
        return refused.code, refused.read().decode("utf-8")


def _wait(browser: Browser, expression: str, seconds: float = 60) -> object:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            value = browser._evaluate(expression)
        except Exception:  # noqa: BLE001 - the page may be between documents
            value = None
        if value:
            return value
        time.sleep(0.2)
    raise AssertionError(expression)


def test_the_address_without_the_token_holds_no_secret_and_lets_nothing_in(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    with _served(config, layout, _Model("none", {})) as server:
        base = server.address.split("?", 1)[0]
        token = server.address.split("token=", 1)[1]
        status, body = _get(base)
        assert status == 401 and "sessionStorage" in body
        assert token not in body and "conversation" not in body.lower()
        status, body = _get(base + "?token=not-the-token")
        assert status == 401 and body == "Open the address this command printed."
        assert _get(base + "api/conversations")[0] == 401


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_reload_keeps_the_page_and_a_token_of_an_earlier_run_is_not_tried_again(
    tmp_path: Path,
) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    with _served(config, layout, _Model("none", {})) as server:
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()
        try:
            browser.navigate(server.address)
            _wait(browser, SEND_READY)
            assert "token" not in str(browser._evaluate("location.href"))

            # F5: the browser asks for the address it shows, which has no token.
            browser.page().call("Page.reload", ignoreCache=True)
            time.sleep(1)
            _wait(browser, SEND_READY)
            assert "token" not in str(browser._evaluate("location.href"))
            # And again: each load keeps it for the next.
            browser.page().call("Page.reload", ignoreCache=True)
            time.sleep(1)
            _wait(browser, SEND_READY)

            # A token from an earlier run, as after a restart: refused, and not tried again.
            browser._evaluate("sessionStorage.setItem('aep-page-token', 'from-an-earlier-run')")
            browser.page().call("Page.reload", ignoreCache=True)
            time.sleep(1)
            _wait(browser, "document.body && document.body.innerText.includes('Open the address')")
            browser.page().call("Page.reload", ignoreCache=True)
            time.sleep(1)
            # Refused again, with nothing tried: no loop, no page, and nothing kept to try.
            said = str(_wait(browser, "document.body && document.body.innerText"))
            assert "Open the address" in said
            assert not browser._evaluate("!!document.getElementById('send')")
            assert not browser._evaluate("sessionStorage.getItem('aep-page-token')")
        finally:
            browser.close()


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_a_new_tab_without_the_token_is_told_to_use_the_shortcut(tmp_path: Path) -> None:
    config, layout = _bi_host(tmp_path / "pc")
    with _served(config, layout, _Model("none", {})) as server:
        base = server.address.split("?", 1)[0]
        browser = Browser(tmp_path / "browser", timeout_s=60)
        browser.start()
        try:
            browser.navigate(base)
            said = str(_wait(browser, "document.body && document.body.innerText"))
            assert "AEP Agent" in said and "重新開啟" in said
            assert not browser._evaluate("!!document.getElementById('send')")
        finally:
            browser.close()
