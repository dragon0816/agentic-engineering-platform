"""Native hover revalidates the target before a single trusted press."""

import json
import sys
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from evaluation.sop_practice import PracticeSite
from integrations.browser import Browser, BrowserError
from integrations.web_script import (
    ScriptMode,
    ScriptRunner,
    WebAction,
    WebScript,
    WebScriptError,
    WebTarget,
)
from integrations.websocket import WebSocketError


@pytest.fixture(scope="module")
def local_page(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Browser, PracticeSite]]:
    if sys.platform != "win32":
        pytest.skip("drives installed Edge")
    site = PracticeSite()
    site.start()
    try:
        with Browser(
            tmp_path_factory.mktemp("hover-profile"), timeout_s=5, viewport=(1440, 900)
        ) as browser:
            browser.navigate(site.url, settle_s=0)
            yield browser, site
    finally:
        site.close()


class ObservedPage:
    def __init__(self, browser: Browser) -> None:
        self.browser = browser
        self.presses = 0
        self.hovers = 0

    def evaluate(self, expression: str) -> Any:
        return self.browser.evaluate(expression)

    def click_at(self, x: float, y: float) -> None:
        self.presses += 1
        self.browser.click_at(x, y)

    def hover_at(self, x: float, y: float, *, timeout_s: float) -> None:
        self.hovers += 1
        self.browser.hover_at(x, y, timeout_s=timeout_s)


def prepare(browser: Browser, on_enter: str = "") -> None:
    browser.page().call("Input.dispatchMouseEvent", type="mouseMoved", x=5, y=5, buttons=0)
    browser.evaluate(
        "(() => {document.body.innerHTML='<button id=control "
        'style="position:fixed;left:200px;top:200px;width:160px;height:60px">'
        "Local control</button>';"
        "window.hoverOK=false;window.pressedOK=false;window.activated=0;window.decoyClicks=0;"
        "const c=document.getElementById('control');"
        "c.addEventListener('pointerenter', e=>{if(e.buttons===0)window.hoverOK=true;"
        + on_enter
        + "});"
        "c.addEventListener('pointerdown',e=>{window.pressedOK=e.buttons===1&&e.isTrusted;});"
        "c.addEventListener('click',()=>{if(window.hoverOK&&window.pressedOK)window.activated++;});"
        "return true;})()"
    )


def click(page: Any, site: PracticeSite, mode: ScriptMode = "act", timeout_s: float = 2) -> None:
    ScriptRunner(page, (site.url,), timeout_s=timeout_s, settle_s=0).run(
        WebScript(actions=(WebAction(do="click", target=WebTarget(css="#control")),)),
        mode,
    )


def test_hover_gate_receives_unpressed_entry_then_one_trusted_press(
    local_page: tuple[Browser, PracticeSite],
) -> None:
    browser, site = local_page
    prepare(browser)
    page = ObservedPage(browser)
    click(page, site)
    assert browser.evaluate("window.activated") == 1
    assert page.presses == 1 and page.hovers == 1


def test_hover_moving_target_is_reobserved_before_pressing_old_decoy(
    local_page: tuple[Browser, PracticeSite],
) -> None:
    browser, site = local_page
    prepare(
        browser,
        "if(!window.moved){window.moved=true;c.style.left='500px';"
        "const decoy=document.createElement('button');decoy.id='decoy';"
        "decoy.style='position:fixed;left:200px;top:200px;width:160px;height:60px';"
        "decoy.textContent='Decoy';decoy.onclick=()=>window.decoyClicks++;document.body.append(decoy);}",
    )
    browser.evaluate("window.moved=false;true")
    page = ObservedPage(browser)
    click(page, site, timeout_s=1)
    assert browser.evaluate("window.activated") == 1
    assert browser.evaluate("window.decoyClicks") == 0
    assert page.presses == 1 and page.hovers == 2


@pytest.mark.parametrize(
    "mutation,code",
    [
        (
            "const cover=document.createElement('div');"
            "cover.style='position:fixed;inset:0;z-index:9999';document.body.append(cover);",
            "web_target_obscured",
        ),
        (
            "const duplicate=c.cloneNode(true);duplicate.style.left='500px';"
            "document.body.append(duplicate);",
            "web_target_ambiguous",
        ),
    ],
)
def test_hover_changes_cannot_bypass_hit_test_or_uniqueness(
    local_page: tuple[Browser, PracticeSite], mutation: str, code: str
) -> None:
    browser, site = local_page
    prepare(browser, mutation)
    page = ObservedPage(browser)
    with pytest.raises(WebScriptError) as failed:
        click(page, site)
    assert failed.value.code == code
    assert page.presses == 0 and page.hovers == 1


def test_read_refusal_happens_before_hover_or_press(
    local_page: tuple[Browser, PracticeSite],
) -> None:
    browser, site = local_page
    prepare(browser)
    page = ObservedPage(browser)
    with pytest.raises(WebScriptError, match="web_click_not_read_only"):
        click(page, site, "read")
    assert page.presses == page.hovers == 0


class SyntheticPointerPage:
    def __init__(self, *, forbidden: bool = False, lost: bool = False) -> None:
        self.hovered = False
        self.forbidden = forbidden
        self.lost = lost
        self.presses = 0
        self.hovers = 0

    def navigate(self, url: str) -> None:
        raise AssertionError("no navigation")

    def reload(self, *, check_origin: Callable[[str], None], timeout_s: float) -> None:
        raise AssertionError("no reload")

    def evaluate(self, expression: str) -> str:
        if expression == "document.location.href":
            return (
                "https://forbidden.test/"
                if self.hovered and self.forbidden
                else "https://allowed.test/"
            )
        return json.dumps({"ok": True, "pointer": {"x": 100, "y": 100}})

    def hover_at(self, x: float, y: float, *, timeout_s: float) -> None:
        self.hovered = True
        self.hovers += 1
        if self.lost:
            raise WebSocketError("closed")

    def click_at(self, x: float, y: float) -> None:
        self.presses += 1


def test_hover_origin_change_causes_zero_presses() -> None:
    page = SyntheticPointerPage(forbidden=True)
    with pytest.raises(WebScriptError, match="web_origin_not_allowed"):
        ScriptRunner(page, ("https://allowed.test",))._perform(
            {"op": "click", "mode": "act", "css": "button"}
        )
    assert page.hovers == 1 and page.presses == 0


def test_hover_socket_failure_does_not_retry_or_press() -> None:
    page = SyntheticPointerPage(lost=True)
    with pytest.raises(WebSocketError, match="closed"):
        ScriptRunner(page, ("https://allowed.test",))._perform(
            {"op": "click", "mode": "act", "css": "button"}
        )
    assert page.hovers == 1 and page.presses == 0


def test_hover_consumes_original_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("integrations.web_script.time.monotonic", lambda: clock[0])

    class SlowHover(SyntheticPointerPage):
        def hover_at(self, x: float, y: float, *, timeout_s: float) -> None:
            super().hover_at(x, y, timeout_s=timeout_s)
            assert 0 < timeout_s <= 1
            clock[0] += 2

    page = SlowHover()
    with pytest.raises(WebScriptError, match="web_wait_timeout"):
        ScriptRunner(page, ("https://allowed.test",), timeout_s=1)._perform(
            {"op": "click", "mode": "act", "css": "button"}
        )
    assert page.hovers == 1 and page.presses == 0


@pytest.mark.parametrize("lost", [False, True])
def test_browser_hover_bounds_single_move_and_restores_timeout(lost: bool) -> None:
    class HoverSocket:
        timeout_s = 30.0

        def __init__(self) -> None:
            self.calls: list[tuple[str, dict[str, Any], float]] = []

        def call(self, method: str, **params: Any) -> dict[str, Any]:
            self.calls.append((method, params, self.timeout_s))
            if lost:
                raise WebSocketError("closed")
            return {}

    socket = HoverSocket()
    browser = Browser.__new__(Browser)
    browser._page = socket  # type: ignore[assignment]
    if lost:
        with pytest.raises(BrowserError, match="click_failed"):
            browser.hover_at(42, 84, timeout_s=0.25)
    else:
        browser.hover_at(42, 84, timeout_s=0.25)
    assert socket.calls == [
        (
            "Input.dispatchMouseEvent",
            {"type": "mouseMoved", "x": 42, "y": 84, "button": "none", "buttons": 0},
            0.25,
        )
    ]
    assert socket.timeout_s == 30


def test_hover_does_not_replay_a_press_that_loses_its_socket() -> None:
    class LostPress(SyntheticPointerPage):
        def click_at(self, x: float, y: float) -> None:
            self.presses += 1
            raise WebSocketError("closed")

    page = LostPress()
    with pytest.raises(WebSocketError, match="closed"):
        ScriptRunner(page, ("https://allowed.test",))._perform(
            {"op": "click", "mode": "act", "css": "button"}
        )
    assert page.hovers == 1 and page.presses == 1


def test_moving_hover_points_share_original_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("integrations.web_script.time.monotonic", lambda: clock[0])

    class Moving(SyntheticPointerPage):
        def evaluate(self, expression: str) -> str:
            if expression == "document.location.href":
                return super().evaluate(expression)
            return json.dumps({"ok": True, "pointer": {"x": 100 + self.hovers * 10, "y": 100}})

        def hover_at(self, x: float, y: float, *, timeout_s: float) -> None:
            super().hover_at(x, y, timeout_s=timeout_s)
            clock[0] += 0.4

    page = Moving()
    with pytest.raises(WebScriptError, match="web_wait_timeout"):
        ScriptRunner(page, ("https://allowed.test",), timeout_s=1)._perform(
            {"op": "click", "mode": "act", "css": "button"}
        )
    assert page.hovers == 3 and page.presses == 0


def test_legacy_native_page_without_hover_keeps_single_probe_behavior() -> None:
    class Legacy:
        def __init__(self) -> None:
            self.page = SyntheticPointerPage()
            self.probes = 0

        def navigate(self, url: str) -> None:
            self.page.navigate(url)

        def reload(self, *, check_origin: Callable[[str], None], timeout_s: float) -> None:
            self.page.reload(check_origin=check_origin, timeout_s=timeout_s)

        def evaluate(self, expression: str) -> str:
            if expression != "document.location.href":
                self.probes += 1
            return self.page.evaluate(expression)

        def click_at(self, x: float, y: float) -> None:
            self.page.click_at(x, y)

    page = Legacy()
    ScriptRunner(page, ("https://allowed.test",))._perform(
        {"op": "click", "mode": "act", "css": "button"}
    )
    assert page.probes == 1 and page.page.presses == 1 and page.page.hovers == 0
