"""A dropped socket to a freshly started browser's first tab is not the end.

CI 2026-10-19: Chrome replaced its first tab right after start and the socket
to it was aborted (WinError 10053) under the first `Page.navigate`.
"""

from typing import Any

import pytest

from integrations.browser import Browser, BrowserError
from integrations.websocket import WebSocketError


class Tab:
    def __init__(self, fail: bool) -> None:
        self.fail = fail
        self.calls: list[str] = []
        self.closed = False

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        self.calls.append(method)
        if self.fail:
            raise WebSocketError("closed")
        return {}

    def close(self) -> None:
        self.closed = True


def browser_with(tabs: list[Tab]) -> Browser:
    browser = Browser.__new__(Browser)
    browser._page = tabs.pop(0)  # type: ignore[assignment]

    def page(*, within_s: float | None = None) -> Any:
        if browser._page is None:
            browser._page = tabs.pop(0)  # type: ignore[assignment]
        return browser._page

    browser.page = page  # type: ignore[method-assign]
    browser._await_load = lambda page: None  # type: ignore[method-assign]
    # A browser that still answers on its port: lost tabs are reattached.
    browser._port = 1
    browser._still_answering = lambda port: True  # type: ignore[method-assign]
    return browser


def test_a_lost_first_tab_is_reattached_once() -> None:
    old, new = Tab(fail=True), Tab(fail=False)
    browser = browser_with([old, new])
    browser.navigate("http://127.0.0.1/", settle_s=0)
    assert old.calls == ["Page.navigate"] and new.calls == ["Page.navigate"]
    # The lost socket is closed rather than left for the collector.
    assert old.closed and not new.closed


def test_a_second_loss_is_a_navigation_failure() -> None:
    browser = browser_with([Tab(fail=True), Tab(fail=True)])
    with pytest.raises(BrowserError) as failed:
        browser.navigate("http://127.0.0.1/", settle_s=0)
    assert failed.value.code == "navigation_failed"


def test_a_tab_lost_while_enabling_is_dropped_and_the_next_one_is_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CI 2026-10-20: the reattached tab dropped during Page.enable."""
    made: list[Any] = []

    class Socket(Tab):
        def __init__(self, url: str, timeout_s: float, trace: object = None) -> None:
            super().__init__(fail=not made)
            made.append(self)

    monkeypatch.setattr("integrations.browser.Devtools", Socket)
    browser = Browser.__new__(Browser)
    browser._page = None
    browser.timeout_s = 5
    target = {"type": "page", "webSocketDebuggerUrl": "ws://127.0.0.1/x"}
    browser._targets = lambda port=None: [target]  # type: ignore[method-assign]
    page: Any = browser.page()
    assert len(made) == 2 and made[0].closed and page is made[1]
    assert made[1].calls == ["Page.enable", "Runtime.enable"]


def test_a_browser_that_went_away_is_launched_again_before_the_retry() -> None:
    """CI 2026-10-20: the reopened profile reached a browser still shutting
    down; it vanished under the first Page.navigate."""
    old, new = Tab(fail=True), Tab(fail=False)
    browser = browser_with([old, new])
    launched: list[str] = []
    browser._port = 1
    browser._still_answering = lambda port: False  # type: ignore[method-assign]
    browser._await_profile_release = lambda: True  # type: ignore[method-assign]
    browser._launch = lambda: launched.append("launch")  # type: ignore[method-assign]
    browser.navigate("http://127.0.0.1/", settle_s=0)
    assert launched == ["launch"] and new.calls == ["Page.navigate"]


def test_a_live_browser_is_only_reattached_not_relaunched() -> None:
    old, new = Tab(fail=True), Tab(fail=False)
    browser = browser_with([old, new])
    launched: list[str] = []
    browser._port = 1
    browser._still_answering = lambda port: True  # type: ignore[method-assign]
    browser._launch = lambda: launched.append("launch")  # type: ignore[method-assign]
    browser.navigate("http://127.0.0.1/", settle_s=0)
    assert launched == [] and new.calls == ["Page.navigate"]
