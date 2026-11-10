"""Desktop viewport is opt-in per attached target, including narrow popups."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from integrations.browser import Browser, browser_path
from integrations.web_script import ScriptRunner, WebAction, WebScript, WebScriptError, WebTarget
from integrations.websocket import Devtools


def test_generic_browser_preserves_default_and_rejects_invalid_viewports(tmp_path: Path) -> None:
    assert Browser(tmp_path / "legacy").viewport is None
    for viewport in ((0, 900), (1440, 0), (10000, 900), (1440, 10000), (True, 900), (1440.0, 900)):
        with pytest.raises(ValueError):
            Browser(tmp_path / "invalid", viewport=viewport)  # type: ignore[arg-type]


def test_aep_browser_factories_choose_the_same_declared_desktop_viewport(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from capabilities.browser_session.handlers import _edge
    from capabilities.web.handlers import OpenPage

    captured: list[dict[str, Any]] = []

    def construct(profile: Path, **options: Any) -> object:
        captured.append(options)
        return object()

    monkeypatch.setattr("integrations.browser.Browser", construct)
    _edge(tmp_path / "conversation", True, 30)
    OpenPage(tmp_path / "workflow", headless=True, timeout_s=30)
    assert [options.get("viewport") for options in captured] == [(1440, 900), (1440, 900)]


@pytest.mark.skipif(sys.platform != "win32", reason="drives isolated installed Edge")
def test_narrow_popup_reaches_desktop_layout_and_native_click_after_reattachment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from evaluation.sop_practice import PracticeSite

    if browser_path() is None:
        pytest.skip("no Chromium browser installed")
    site = PracticeSite()
    site.start()
    try:
        with Browser(tmp_path / "profile", timeout_s=15, viewport=(500, 320)) as browser:
            lines = (browser.profile / "DevToolsActivePort").read_text().splitlines()
            with Devtools(f"ws://127.0.0.1:{lines[0]}{lines[1]}", timeout_s=10) as control:
                created = control.call(
                    "Target.createTarget", url="about:blank", newWindow=True, width=500, height=400
                )
            target = next(
                target for target in browser._targets() if target.get("id") == created["targetId"]
            )
            browser.page().close()
            browser._page = None
            monkeypatch.setattr(browser, "_targets", lambda port=None: [target])
            popup = browser.page()
            # Finish the initial navigation before replacing the fixture DOM.
            browser.navigate(site.url, settle_s=0)
            ready = (
                f"location.href === {json.dumps(site.url.rstrip('/') + '/')} && "
                "document.readyState === 'complete' && !!document.getElementById('customer')"
            )
            load_deadline = time.monotonic() + 10
            while not browser.evaluate(ready):
                assert time.monotonic() < load_deadline, "practice document did not finish loading"
                time.sleep(0.05)
            browser.evaluate(
                "document.body.innerHTML = '<style>#veil{display:none;position:fixed;inset:0;' + "
                "'z-index:100}' + "
                "'@media(max-width:600px){#veil{display:block}}</style>' + "
                '\'<button id="search">Advanced Search</button><div id="veil"></div>\';'
                "window.__nativeClicked=false;document.getElementById('search').addEventListener('mouseup',"
                "e=>window.__nativeClicked=e.isTrusted);"
            )
            action = WebAction(do="click", target=WebTarget(css="#search"))
            runner = ScriptRunner(browser, (site.url,), timeout_s=0.2)
            with pytest.raises(WebScriptError) as failed:
                runner.run(WebScript(actions=(action,)), "act")
            assert failed.value.code == "web_target_obscured"
            assert browser.evaluate("innerWidth") == 500
            # Opt in, then reattach to this same popup, not merely a launch-size flag.
            browser.viewport = (1440, 900)
            popup.close()
            browser._page = None
            browser.page()
            assert browser.evaluate("innerWidth") == 1440
            assert browser.evaluate("innerHeight") == 900
            assert (
                browser.evaluate("getComputedStyle(document.getElementById('veil')).display")
                == "none"
            )
            # This phase tests native input and viewport reattachment, not a .2s deadline.
            ScriptRunner(browser, (site.url,), timeout_s=2).run(WebScript(actions=(action,)), "act")
            assert browser.evaluate("window.__nativeClicked") is True
            assert json.loads(browser.evaluate("JSON.stringify([innerWidth,innerHeight])")) == [
                1440,
                900,
            ]
    finally:
        site.close()
