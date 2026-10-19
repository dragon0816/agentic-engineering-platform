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

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        self.calls.append(method)
        if self.fail:
            raise WebSocketError("closed")
        return {}


def browser_with(tabs: list[Tab]) -> Browser:
    browser = Browser.__new__(Browser)
    browser._page = tabs.pop(0)  # type: ignore[assignment]

    def page() -> Any:
        if browser._page is None:
            browser._page = tabs.pop(0)  # type: ignore[assignment]
        return browser._page

    browser.page = page  # type: ignore[method-assign]
    browser._await_load = lambda page: None  # type: ignore[method-assign]
    return browser


def test_a_lost_first_tab_is_reattached_once() -> None:
    old, new = Tab(fail=True), Tab(fail=False)
    browser = browser_with([old, new])
    browser.navigate("http://127.0.0.1/", settle_s=0)
    assert old.calls == ["Page.navigate"] and new.calls == ["Page.navigate"]


def test_a_second_loss_is_a_navigation_failure() -> None:
    browser = browser_with([Tab(fail=True), Tab(fail=True)])
    with pytest.raises(BrowserError) as failed:
        browser.navigate("http://127.0.0.1/", settle_s=0)
    assert failed.value.code == "navigation_failed"
