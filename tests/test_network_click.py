"""Fresh network completion is atomic with one native click, never business proof."""

import json
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast

import pytest

from integrations.browser import Browser
from integrations.network_barrier import NetworkBarrier
from integrations.web_script import ScriptRunner, WebAction, WebScript, WebScriptError
from integrations.websocket import Devtools, SocketTrace


def test_network_params_are_sanitized_before_queue_pruning_and_diagnostics() -> None:
    raw = {
        "method": "Network.requestWillBeSent",
        "params": {
            "requestId": "one",
            "frameId": "main",
            "type": "Fetch",
            "timestamp": 10.0,
            "request": {
                "url": "https://example.test/data?private=PRIVATE_QUERY",
                "headers": {"Cookie": "PRIVATE_COOKIE" * 1000},
                "postData": "PRIVATE_BODY",
            },
        },
    }
    messages = iter(
        [
            raw,
            {
                "method": "Network.responseReceived",
                "params": {
                    "requestId": "one",
                    "timestamp": 10.5,
                    "type": "Fetch",
                    "response": {"status": 200, "headers": {"Secret": "PRIVATE_RESPONSE"}},
                },
            },
            {"method": "Network.loadingFinished", "params": {"requestId": "one", "timestamp": 11}},
            {"method": "Network.webSocketFrameReceived", "params": {"data": "PRIVATE_FRAME"}},
            {"id": 1, "result": {}},
        ]
    )

    class Socket:
        def send(self, value: str) -> None:
            pass

        def receive(self) -> str:
            return json.dumps(next(messages))

        def _io_timeout(self) -> None:
            pass

    page = cast(Any, object.__new__(Devtools))
    page._last, page.events, page.socket = 0, [], Socket()
    page.trace = SocketTrace()
    tracker = NetworkBarrier(("https://example.test",))
    tracker.arm("main", "https://example.test", 9.0, time.monotonic())
    page.network_observer = tracker

    page._call("Runtime.evaluate", expression="0")

    assert tracker.evidence()["fresh_finished"] == 1
    assert not tracker.evidence()["lost"]
    assert page.events == []
    assert "PRIVATE" not in json.dumps(page.trace.as_record())


@pytest.fixture(scope="module")
def network_site() -> Iterator[tuple[str, threading.Event, threading.Event]]:
    release = threading.Event()
    headers = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/data":
                body = b'[{"ID":"fresh"}]'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.flush()
                headers.set()
                release.wait(5)
            else:
                body = (
                    b'<button id="go">Query</button><table id="rows"><thead><tr><th>ID</th>'
                    b"</tr></thead><tbody><tr><td>old</td></tr></tbody></table><script>"
                    b"window.presses=0;window.trusted=false;go.onclick=e=>{window.presses++;"
                    b'window.trusted=e.isTrusted;fetch("/data").then(r=>r.json()).then(rows=>{'
                    b'document.querySelector("tbody").innerHTML="<tr><td>"+rows[0].ID+"</td></tr>";});'
                    b"};</script>"
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", release, headers
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.skipif(sys.platform != "win32", reason="drives installed Edge on a local fixture")
def test_atomic_native_click_waits_for_fresh_response_body(
    network_site: tuple[str, threading.Event, threading.Event],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url, release, headers = network_site
    release.clear()
    headers.clear()
    observations: list[Any] = []
    event = NetworkBarrier.event
    arm = NetworkBarrier.arm

    def recorded_event(self: NetworkBarrier, method: str, params: Any, now: float) -> None:
        observations.append((method, params))
        event(self, method, params, now)

    def recorded_arm(
        self: NetworkBarrier, frame: str, origin: str, epoch: float, now: float
    ) -> None:
        observations.append(("epoch", frame, origin, epoch))
        arm(self, frame, origin, epoch, now)

    monkeypatch.setattr(NetworkBarrier, "event", recorded_event)
    monkeypatch.setattr(NetworkBarrier, "arm", recorded_arm)

    with Browser(tmp_path / "profile", timeout_s=5) as browser:
        browser.navigate(url, settle_s=0)
        action = WebAction.model_validate({"do": "click_wait_network", "target": {"css": "#go"}})
        completed = threading.Event()
        outcomes: list[Any] = []

        def execute() -> None:
            try:
                outcomes.append(
                    ScriptRunner(browser, (url,), settle_s=0.1, timeout_s=10).run(
                        WebScript(
                            actions=(
                                action,
                                WebAction(do="read_table", table="#rows", save_as="rows"),
                            )
                        ),
                        "act",
                    )
                )
            except Exception as error:
                error.add_note(json.dumps({"events": observations}))
                outcomes.append(error)
            finally:
                completed.set()

        completion = threading.Thread(target=execute, daemon=True)
        completion.start()
        try:
            assert headers.wait(10), outcomes
            assert not completed.wait(0.2), outcomes
        finally:
            release.set()
            completion.join(timeout=12)
        assert not completion.is_alive()
        assert outcomes
        if isinstance(outcomes[0], Exception):
            raise outcomes[0]
        result = outcomes[0]
        assert result.data["rows"] == [{"ID": "fresh"}]
        assert browser.evaluate("window.presses") == 1
        assert browser.evaluate("window.trusted") is True


def test_new_network_action_never_falls_back_to_javascript_or_read_mode() -> None:
    class Page:
        presses = 0

        def evaluate(self, expression: str) -> Any:
            raise AssertionError("read refusal must precede observation or JS click")

    action = WebAction.model_validate({"do": "click_wait_network", "target": {"css": "#go"}})
    with pytest.raises(WebScriptError, match="web_network_click_not_read_only"):
        ScriptRunner(cast(Any, Page()), ("https://example.test",)).run(
            WebScript(actions=(action,)), "read"
        )


def test_network_action_does_not_accept_new_output_or_query_options() -> None:
    from pydantic import ValidationError

    for extra in ({"save_as": "network"}, {"url": "https://example.test"}, {"value": "private"}):
        with pytest.raises(ValidationError):
            WebAction.model_validate(
                {"do": "click_wait_network", "target": {"css": "#go"}, **extra}
            )


@pytest.mark.skipif(sys.platform != "win32", reason="drives installed Edge on a local fixture")
def test_two_atomic_actions_each_press_once_and_require_their_own_request(
    network_site: tuple[str, threading.Event, threading.Event], tmp_path: Path
) -> None:
    url, release, _headers = network_site
    release.set()
    with Browser(tmp_path / "profile", timeout_s=5) as browser:
        action = WebAction.model_validate({"do": "click_wait_network", "target": {"css": "#go"}})
        ScriptRunner(browser, (url,), settle_s=0.05, timeout_s=3).run(
            WebScript(actions=(WebAction(do="open", url=url), action, action)), "act"
        )
        assert browser.evaluate("window.presses") == 2
        assert browser.evaluate("window.trusted") is True


@pytest.mark.skipif(sys.platform != "win32", reason="drives installed Edge on a local fixture")
@pytest.mark.parametrize("change", ["overlay", "move"])
def test_fence_dom_change_cannot_press_the_old_point(
    network_site: tuple[str, threading.Event, threading.Event],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    from integrations.browser import _NetworkObservation

    url, release, _headers = network_site
    release.set()
    arm = _NetworkObservation.arm
    with Browser(tmp_path / "profile", timeout_s=5) as browser:
        browser.navigate(url, settle_s=0)

        def changed(self: Any, check_origin: Any) -> None:
            arm(self, check_origin)
            if change == "overlay":
                browser.evaluate(
                    "document.body.insertAdjacentHTML('beforeend',"
                    "'<div style=\"position:fixed;inset:0;z-index:99999\"></div>')"
                )
            else:
                browser.evaluate("go.style.marginLeft='200px'")

        monkeypatch.setattr(_NetworkObservation, "arm", changed)
        action = WebAction.model_validate({"do": "click_wait_network", "target": {"css": "#go"}})
        with pytest.raises(
            WebScriptError,
            match="web_target_obscured|web_target_changed|web_network_observation_lost",
        ):
            ScriptRunner(browser, (url,), timeout_s=3).run(WebScript(actions=(action,)), "act")
        assert browser.evaluate("window.presses") == 0


def test_observer_cleanup_cannot_reset_an_exhausted_action_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    now = 0.0
    monkeypatch.setattr(time, "monotonic", lambda: now)

    class Page:
        network_observer: Any = None
        network_events_lost = False
        calls: list[str] = []

        def call(self, method: str, **params: Any) -> dict[str, Any]:
            self.calls.append(method)
            return {}

        @contextmanager
        def within_deadline(self, deadline: float) -> Iterator[None]:
            yield

    browser = Browser(tmp_path / "unused-profile", timeout_s=1)
    page = Page()
    browser._page = cast(Any, page)
    with browser.observe_network(("https://example.test",)) as observer:
        with observer.within_deadline(1.0):
            now = 2.0
    assert page.calls == ["Network.enable", "Performance.enable"]
    assert page.network_observer is None


def test_known_observation_loss_refuses_the_before_press_callback(tmp_path: Path) -> None:
    from integrations.browser import BrowserError, _NetworkObservation

    class Page:
        network_events_lost = False
        network_observer: Any = None

        def call(self, method: str, **params: Any) -> dict[str, Any]:
            if method == "Page.getFrameTree":
                return {"frameTree": {"frame": {"id": "main", "url": "https://example.test"}}}
            return {"metrics": [{"name": "Timestamp", "value": 10.0}]}

    browser = Browser(tmp_path / "unused-profile")
    page = Page()
    browser._page = cast(Any, page)
    observer = _NetworkObservation(browser, cast(Any, page), ("https://example.test",))
    page.network_observer = observer.tracker
    observer.tracker.mark_lost()
    presses = 0
    with pytest.raises(BrowserError, match="web_network_observation_lost"):
        observer.arm(lambda url: None)
        presses += 1
    assert presses == 0


def test_outer_action_deadline_survives_commands_and_restores_socket(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Socket:
        _deadline: float | None = None
        timeout = 7.0

        def gettimeout(self) -> float:
            return self.timeout

        def settimeout(self, value: float) -> None:
            self.timeout = value

    transport = Socket()
    page = cast(Any, object.__new__(Devtools))
    page.timeout_s = 30.0
    page.socket = type("Transport", (), {"_deadline": None, "socket": transport})()
    monkeypatch.setattr(time, "monotonic", lambda: 100.0)
    calls = 0

    def command(method: str, **params: Any) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        assert page.socket._deadline == 101.0
        transport.settimeout(0.5)
        if calls == 2:
            raise RuntimeError("single failure, no replay")
        return {}

    page._call = command
    with pytest.raises(RuntimeError, match="single failure"):
        with page.within_deadline(101.0):
            page.call("first")
            page.call("second")
    assert calls == 2
    assert page.socket._deadline is None
    assert transport.gettimeout() == 7.0


@pytest.mark.skipif(sys.platform != "win32", reason="drives installed Edge on a local fixture")
def test_fence_origin_switch_never_presses_a_different_allowed_page(
    network_site: tuple[str, threading.Event, threading.Event],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from integrations.browser import _NetworkObservation

    url, release, _headers = network_site
    other = url.replace("127.0.0.1", "localhost")
    release.set()
    with Browser(tmp_path / "profile", timeout_s=5) as browser:
        browser.navigate(url, settle_s=0)
        original = _NetworkObservation.arm

        def navigate_after_arm(self: Any, check_origin: Any) -> None:
            original(self, check_origin)
            browser.navigate(other, settle_s=0)

        monkeypatch.setattr(_NetworkObservation, "arm", navigate_after_arm)
        action = WebAction.model_validate({"do": "click_wait_network", "target": {"css": "#go"}})
        with pytest.raises(WebScriptError, match="web_origin_not_allowed"):
            ScriptRunner(browser, (url, other), settle_s=0, timeout_s=3).run(
                WebScript(actions=(action,)), "act"
            )
        assert browser.evaluate("window.presses") == 0
