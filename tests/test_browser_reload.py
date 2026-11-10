"""Explicit reload rebuilds an existing document without replaying navigation."""

import sys
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from integrations.browser import Browser, BrowserError
from integrations.web_script import ScriptRunner, WebAction, WebScript, WebScriptError


class ReloadTab:
    def __init__(self, *, changes: bool = True, redirect: bool = False) -> None:
        self.timeout_s = 30.0
        self.calls: list[str] = []
        self.budgets: list[float] = []
        self.loaded = False
        self.changes = changes
        self.redirect = redirect

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        self.calls.append(method)
        self.budgets.append(self.timeout_s)
        url = "https://other.test/" if self.loaded and self.redirect else "https://allowed.test/"
        if method == "Page.getFrameTree":
            return {
                "frameTree": {
                    "frame": {
                        "id": "main",
                        "loaderId": "new" if self.loaded and self.changes else "old",
                        "url": url,
                    }
                }
            }
        if method == "Page.reload":
            self.loaded = True
            return {}
        if method == "Runtime.evaluate":
            return {"result": {"value": {"ready": "complete", "url": url}}}
        raise AssertionError(method)


def fake_browser(tab: ReloadTab) -> Browser:
    browser = Browser.__new__(Browser)
    browser._page = tab  # type: ignore[assignment]
    browser.timeout_s = 0.08
    return browser


def test_reload_waits_for_new_loader_and_bounds_every_command() -> None:
    tab = ReloadTab()
    checked: list[str] = []
    fake_browser(tab).reload(check_origin=checked.append)
    assert tab.calls.count("Page.reload") == 1
    assert tab.calls[0] == "Page.getFrameTree"
    assert "Runtime.evaluate" in tab.calls
    assert checked and set(checked) == {"https://allowed.test/"}
    assert all(0 < budget <= 0.080001 for budget in tab.budgets)
    assert tab.timeout_s == 30


def test_old_complete_document_does_not_satisfy_reload() -> None:
    tab = ReloadTab(changes=False)
    with pytest.raises(BrowserError) as error:
        fake_browser(tab).reload()
    assert error.value.code == "navigation_failed"
    assert tab.calls.count("Page.reload") == 1
    assert "Runtime.evaluate" not in tab.calls
    assert tab.timeout_s == 30


def test_reload_origin_redirect_is_refused_without_retry() -> None:
    tab = ReloadTab(redirect=True)

    def check(url: str) -> None:
        if url != "https://allowed.test/":
            raise WebScriptError("web_origin_not_allowed")

    with pytest.raises(WebScriptError, match="web_origin_not_allowed"):
        fake_browser(tab).reload(check_origin=check)
    assert tab.calls.count("Page.reload") == 1
    assert "Runtime.evaluate" not in tab.calls
    assert tab.timeout_s == 30


@pytest.mark.parametrize(
    "extra",
    [
        {"url": "https://allowed.test/"},
        {"target": {"css": "body"}},
        {"trigger": {"css": "button"}},
        {"value": "x"},
        {"scope": "main"},
        {"offset": 1},
        {"limit": 20},
        {"save_as": "x"},
        {"table": "table"},
    ],
)
def test_reload_accepts_no_action_arguments(extra: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        WebAction.model_validate({"do": "reload", **extra})


def test_read_mode_refuses_reload_before_any_page_call() -> None:
    class UnusedPage:
        def evaluate(self, expression: str) -> Any:
            raise AssertionError("read reload must not inspect or operate page")

    with pytest.raises(WebScriptError, match="web_reload_not_read_only"):
        ScriptRunner(UnusedPage(), ("https://allowed.test",)).run(  # type: ignore[arg-type]
            WebScript(actions=(WebAction(do="reload"),)), "read"
        )


@pytest.mark.skipif(sys.platform != "win32", reason="drives installed Edge")
def test_reload_rebuilds_local_hash_spa_and_preserves_viewport(tmp_path: Path) -> None:
    from evaluation.sop_practice import PracticeSite

    site = PracticeSite()
    site.start()
    try:
        with Browser(tmp_path / "profile", timeout_s=10, viewport=(1440, 900)) as browser:
            browser.navigate(site.url + "/#orders", settle_s=0)
            browser.evaluate(
                "window.localSentinel=true;document.body.insertAdjacentHTML("
                "'beforeend','<div id=modal role=dialog>Local modal</div>');true"
            )
            browser.timeout_s = 0.15
            browser.navigate(site.url + "/#home", settle_s=0)
            assert browser.evaluate(
                "!!document.getElementById('modal') && window.localSentinel===true"
            )
            browser.timeout_s = 10
            result = ScriptRunner(browser, (site.url,)).run(
                WebScript(actions=(WebAction(do="reload"),)), "act"
            )
            assert result.url.endswith("/#home")
            assert browser.evaluate(
                "!document.getElementById('modal') && window.localSentinel===undefined"
            )
            assert browser.evaluate("innerWidth") == 1440
    finally:
        site.close()


def test_reload_refuses_current_origin_before_reloading() -> None:
    tab = ReloadTab()

    def refuse(url: str) -> None:
        raise WebScriptError("web_origin_not_allowed")

    with pytest.raises(WebScriptError, match="web_origin_not_allowed"):
        fake_browser(tab).reload(check_origin=refuse)
    assert tab.calls == ["Page.getFrameTree"]


def test_reload_missing_initial_loader_is_not_retried() -> None:
    class MissingLoader(ReloadTab):
        def call(self, method: str, **params: Any) -> dict[str, Any]:
            answer = super().call(method, **params)
            answer["frameTree"]["frame"].pop("loaderId")
            return answer

    tab = MissingLoader()
    with pytest.raises(BrowserError, match="reload_no_loader"):
        fake_browser(tab).reload()
    assert tab.calls == ["Page.getFrameTree"]


def test_reload_new_document_must_finish_loading() -> None:
    class Loading(ReloadTab):
        def call(self, method: str, **params: Any) -> dict[str, Any]:
            answer = super().call(method, **params)
            if method == "Runtime.evaluate":
                answer["result"]["value"]["ready"] = "loading"
            return answer

    tab = Loading()
    with pytest.raises(BrowserError, match="reload_timeout"):
        fake_browser(tab).reload()
    assert tab.calls.count("Page.reload") == 1
    assert "Runtime.evaluate" in tab.calls


def test_reload_commands_share_one_absolute_deadline(monkeypatch: pytest.MonkeyPatch) -> None:
    clock = [100.0]
    monkeypatch.setattr("integrations.browser.time.monotonic", lambda: clock[0])

    class Slow(ReloadTab):
        def call(self, method: str, **params: Any) -> dict[str, Any]:
            answer = super().call(method, **params)
            clock[0] += 0.05
            return answer

    tab = Slow()
    with pytest.raises(BrowserError, match="reload_timeout"):
        fake_browser(tab).reload()
    assert tab.calls == ["Page.getFrameTree", "Page.reload"]
    assert tab.budgets[1] < tab.budgets[0] / 2
    assert tab.timeout_s == 30


def test_reload_serialized_action_roundtrips_without_extra_authority() -> None:
    action = WebAction(do="reload")
    assert WebAction.model_validate(action.model_dump()) == action


def test_reload_socket_failure_never_replays_or_reattaches() -> None:
    from integrations.websocket import WebSocketError

    class Lost(ReloadTab):
        def call(self, method: str, **params: Any) -> dict[str, Any]:
            answer = super().call(method, **params)
            if method == "Page.reload":
                raise WebSocketError("closed")
            return answer

    tab = Lost()
    with pytest.raises(BrowserError, match="navigation_failed"):
        fake_browser(tab).reload()
    assert tab.calls == ["Page.getFrameTree", "Page.reload"]
    assert tab.timeout_s == 30


class CommitAfterReady(ReloadTab):
    """Document B finishes just before a second navigation commits C."""

    def __init__(self, *, forbidden: bool = False, changes_frame: bool = False) -> None:
        super().__init__()
        self.phase = 1
        self.ready_states: list[str] = []
        self.forbidden = forbidden
        self.changes_frame = changes_frame

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        answer = super().call(method, **params)
        if method == "Page.getFrameTree" and self.loaded:
            frame = answer["frameTree"]["frame"]
            frame["loaderId"] = "B" if self.phase == 1 else "C"
            if self.changes_frame and self.phase > 1:
                frame["id"] = "main-C"
            if self.forbidden and self.phase > 1:
                frame["url"] = "https://forbidden.test/"
        if method == "Runtime.evaluate":
            state = "loading" if self.phase == 2 else "complete"
            answer["result"]["value"]["ready"] = state
            self.ready_states.append(state)
            self.phase += 1
        return answer


@pytest.mark.parametrize("changes_frame", [False, True])
def test_reload_rechecks_document_after_ready_before_returning(changes_frame: bool) -> None:
    tab = CommitAfterReady(changes_frame=changes_frame)
    fake_browser(tab).reload(timeout_s=1)
    assert tab.ready_states == ["complete", "loading", "complete"]
    assert tab.calls[-1] == "Page.getFrameTree"
    assert tab.calls.count("Page.reload") == 1
    assert tab.timeout_s == 30


def test_reload_post_readiness_forbidden_commit_is_refused() -> None:
    tab = CommitAfterReady(forbidden=True)

    def check(url: str) -> None:
        if url != "https://allowed.test/":
            raise WebScriptError("web_origin_not_allowed")

    with pytest.raises(WebScriptError, match="web_origin_not_allowed"):
        fake_browser(tab).reload(check_origin=check, timeout_s=1)
    assert tab.ready_states == ["complete"]
    assert tab.calls.count("Page.reload") == 1
    assert tab.timeout_s == 30
