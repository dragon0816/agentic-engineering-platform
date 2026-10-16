"""One-click Agent Web (owner 2026-10-08): the running server's address is kept
in the workspace, and `open` starts the server when nothing answers."""

from __future__ import annotations

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from host_runtime.launcher import (
    SLOW_START_SECONDS,
    STARTING_HTML,
    STARTING_STATUS,
    LauncherError,
    StartState,
    clear_record,
    console_python,
    open_agent,
    read_record,
    record_path,
    refreshed_environment,
    starting_page,
    write_record,
    write_start_status,
    write_starting_page,
)


class Page(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - base class spelling
        ok = self.path == "/?token=right"
        self.send_response(200 if ok else 401)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
        return None


@pytest.fixture
def server() -> Any:
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Page)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd
    httpd.shutdown()
    httpd.server_close()


def address(httpd: ThreadingHTTPServer, token: str = "right") -> str:
    return f"http://127.0.0.1:{httpd.server_address[1]}/?token={token}"


def test_the_record_belongs_to_the_server_that_wrote_it(tmp_path: Path) -> None:
    write_record(tmp_path, "http://127.0.0.1:1/?token=x", 1)
    assert read_record(tmp_path)["pid"] == os.getpid()  # type: ignore[index]
    record_path(tmp_path).write_text(json.dumps({"address": "a", "pid": -1}), encoding="utf-8")
    clear_record(tmp_path)  # another process's record stays
    assert read_record(tmp_path) is not None
    write_record(tmp_path, "http://127.0.0.1:1/?token=x", 1)
    clear_record(tmp_path)
    assert read_record(tmp_path) is None


def test_a_running_server_is_opened_without_starting_another(
    tmp_path: Path,
    server: ThreadingHTTPServer,
) -> None:
    write_record(tmp_path, address(server), server.server_address[1])
    opened: list[str] = []

    def never() -> None:
        raise AssertionError("must not start a second server")

    assert (
        open_agent(tmp_path, tmp_path / "host.json", start=never, opener=opened.append) == "opened"
    )
    assert opened == [address(server)]


def test_a_stale_record_is_dropped_and_the_server_started_then_opened(
    tmp_path: Path,
    server: ThreadingHTTPServer,
) -> None:
    write_record(tmp_path, address(server, "old-token"), 1)  # from a server that died
    opened: list[str] = []
    started: list[bool] = []

    def start() -> None:
        started.append(True)
        write_record(tmp_path, address(server), server.server_address[1])

    assert (
        open_agent(
            tmp_path,
            tmp_path / "host.json",
            start=start,
            opener=opened.append,
            poll=0.01,
            handoff_seconds=0,
        )
        == "started"
    )
    # The starting page was opened at once; the page goes on to Agent Web.
    assert started == [True] and opened == [starting_page(tmp_path).as_uri()]


def test_a_server_that_never_answers_is_reported_with_where_to_look(tmp_path: Path) -> None:
    with pytest.raises(LauncherError) as failed:
        open_agent(
            tmp_path,
            tmp_path / "host.json",
            start=lambda: None,
            opener=print,
            wait_seconds=0.05,
            poll=0.01,
        )
    assert failed.value.code == "agent_web_not_started" and "logs" in str(failed.value)
    # The starting page says so too, with where the log is.
    status = _status(tmp_path)
    assert status["state"] == "failed" and "did not answer" in status["message"]
    assert status["logs"] == str(tmp_path / "logs") and "address" not in status


def test_the_environment_keeps_this_process_values_and_the_console_python(
    tmp_path: Path,
) -> None:
    env = refreshed_environment({"KEEP": "1"})
    assert env["KEEP"] == "1"
    windowless = tmp_path / "pythonw.exe"
    windowless.write_text("")
    (tmp_path / "python.exe").write_text("")
    assert console_python(str(windowless)) == str(tmp_path / "python.exe")
    assert console_python("C:/x/python.exe") == "C:/x/python.exe"


# --- the starting page (owner 2026-10-16) ------------------------------------------


def _status(workspace: Path) -> dict[str, Any]:
    text = (workspace / STARTING_STATUS).read_text(encoding="utf-8").rstrip()
    prefix = "window.aepStarting && window.aepStarting("
    assert text.startswith(prefix) and text.endswith(");")
    value: dict[str, Any] = json.loads(text[len(prefix) : -2])
    return value


def _page(workspace: Path, state: StartState, started_ms: float) -> Path:
    write_start_status(workspace, state, started_ms=int(started_ms))
    return write_starting_page(workspace)


def test_the_starting_page_is_static_and_holds_no_address() -> None:
    assert "token" not in STARTING_HTML.lower()
    assert "127.0.0.1:" not in STARTING_HTML and "?token" not in STARTING_HTML
    assert "prefers-color-scheme: dark" in STARTING_HTML
    assert 'name="color-scheme" content="light dark"' in STARTING_HTML
    assert f"{STARTING_STATUS}?t=" in STARTING_HTML
    assert f"var SLOW = {SLOW_START_SECONDS} * 1000" in STARTING_HTML
    assert "AEP Agent is starting" in STARTING_HTML and "agent-web-*.err.log" in STARTING_HTML
    assert "__SLOW__" not in STARTING_HTML and "__STATUS__" not in STARTING_HTML


def test_only_the_ready_status_carries_the_address(tmp_path: Path) -> None:
    given = "http://127.0.0.1:1/?token=x"
    states: tuple[StartState, ...] = ("starting", "failed", "opened")
    for state in states:
        write_start_status(tmp_path, state, started_ms=1, address=given)
        assert "address" not in _status(tmp_path)
        assert "token" not in json.dumps(_status(tmp_path))
    write_start_status(tmp_path, "ready", started_ms=1, address=given)
    assert _status(tmp_path)["address"] == given


def test_the_page_is_shown_first_and_handed_the_address_then_it_is_removed(
    tmp_path: Path, server: ThreadingHTTPServer
) -> None:
    opened: list[str] = []
    seen: list[dict[str, Any]] = []
    states: list[str] = []

    def opener(url: str) -> bool:
        opened.append(url)
        return True

    def start() -> None:
        # The page is already open, saying "starting", before the server starts.
        assert opened == [starting_page(tmp_path).as_uri()]
        states.append(_status(tmp_path)["state"])
        write_record(tmp_path, address(server), server.server_address[1])

    def sleep(seconds: float) -> None:
        seen.append(_status(tmp_path))

    outcome = open_agent(
        tmp_path,
        tmp_path / "host.json",
        start=start,
        opener=opener,
        poll=0.01,
        handoff_seconds=7,
        sleep=sleep,
    )
    assert outcome == "started" and states == ["starting"]
    assert opened == [starting_page(tmp_path).as_uri()]  # Agent Web is opened by the page
    assert seen[-1]["state"] == "ready" and seen[-1]["address"] == address(server)
    final = _status(tmp_path)
    assert final["state"] == "opened" and "address" not in final
    # The address is in agent-web.json, as before, and in no other file.
    holding = [
        path.name
        for path in tmp_path.rglob("*")
        if path.is_file() and "token=right" in path.read_text(encoding="utf-8")
    ]
    assert holding == ["agent-web.json"]


def test_without_a_browser_for_the_page_agent_web_is_opened_directly(
    tmp_path: Path, server: ThreadingHTTPServer
) -> None:
    opened: list[str] = []

    def opener(url: str) -> bool:
        opened.append(url)
        return not url.startswith("file:")

    outcome = open_agent(
        tmp_path,
        tmp_path / "host.json",
        start=lambda: write_record(tmp_path, address(server), server.server_address[1]),
        opener=opener,
        poll=0.01,
    )
    assert outcome == "started" and opened[-1] == address(server)
    assert _status(tmp_path)["state"] == "starting"


def test_a_server_that_exits_while_starting_is_reported_at_once(tmp_path: Path) -> None:
    class Exited:
        def poll(self) -> int:
            return 3

    begun = time.monotonic()
    with pytest.raises(LauncherError) as failed:
        open_agent(tmp_path, tmp_path / "host.json", start=Exited, opener=lambda _: True, poll=0.01)
    assert time.monotonic() - begun < 5
    assert failed.value.code == "agent_web_exited" and "exit code 3" in str(failed.value)
    status = _status(tmp_path)
    assert status["state"] == "failed" and "exit code 3" in status["message"]


# --- the starting page in a real browser --------------------------------------------


def _browser_missing() -> bool:
    from integrations.browser import browser_path

    return browser_path() is None


def _now_ms() -> int:
    return int(time.time() * 1000)


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_starting_page_waits_then_goes_to_agent_web_in_a_real_browser(
    tmp_path: Path, server: ThreadingHTTPServer
) -> None:
    """Measured: the card and spinner are laid out, the elapsed time runs, a
    start of over two minutes says where the log is, the dark scheme applies,
    and `ready` takes the browser to Agent Web's address."""
    from integrations.browser import Browser

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    page = _page(workspace, "starting", _now_ms())
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()

    def wait(expression: str, seconds: float = 20) -> object:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            value = browser._evaluate(expression)
            if value:
                return value
            time.sleep(0.2)
        raise AssertionError(expression)

    def measure(selector: str) -> list[int]:
        size: list[int] = json.loads(
            str(
                browser._evaluate(
                    "JSON.stringify((() => { const r = document.querySelector("
                    + json.dumps(selector)
                    + ").getBoundingClientRect();"
                    " return [Math.round(r.width), Math.round(r.height)]; })())"
                )
            )
        )
        return size

    try:
        browser.navigate(page.as_uri())
        wait('document.getElementById("elapsed").textContent !== "0:00"', 10)
        card_w, card_h = measure("main")
        # Its layout box, not the bounding box of the rotating ring.
        spin_w, spin_h = json.loads(
            str(
                browser._evaluate(
                    'JSON.stringify([document.getElementById("spinner").offsetWidth,'
                    ' document.getElementById("spinner").offsetHeight])'
                )
            )
        )
        assert card_w >= 300 and card_h >= 180, (card_w, card_h)
        assert spin_w == 48 and spin_h == 48, (spin_w, spin_h)
        slow_display = 'getComputedStyle(document.getElementById("slow")).display'
        assert browser._evaluate(slow_display) == "none"
        light = browser._evaluate("getComputedStyle(document.body).backgroundColor")
        browser.page().call(
            "Emulation.setEmulatedMedia",
            features=[{"name": "prefers-color-scheme", "value": "dark"}],
        )
        dark = browser._evaluate("getComputedStyle(document.body).backgroundColor")
        assert light != dark, (light, dark)
        # Two minutes and more: say it is slow, and where the log is.
        write_start_status(workspace, "starting", started_ms=_now_ms() - 125_000)
        wait(slow_display + ' === "block"')
        slow_w, slow_h = measure("#slow")
        assert slow_w >= 250 and slow_h >= 60, (slow_w, slow_h)
        assert str(workspace / "logs") in str(browser._evaluate("document.body.innerText"))
        print(f"starting card {card_w}x{card_h}, spinner {spin_w}x{spin_h}, slow {slow_w}x{slow_h}")
        # Ready: the page goes to Agent Web's address.
        write_start_status(workspace, "ready", started_ms=_now_ms(), address=address(server))
        wait(f"location.href === {json.dumps(address(server))}")
    finally:
        browser.close()


@pytest.mark.skipif(_browser_missing(), reason="no Chromium browser is installed")
def test_the_starting_page_shows_a_failure_in_a_real_browser(tmp_path: Path) -> None:
    from integrations.browser import Browser

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    page = _page(workspace, "starting", _now_ms())
    browser = Browser(tmp_path / "browser", timeout_s=60)
    browser.start()
    try:
        browser.navigate(page.as_uri())
        write_start_status(workspace, "failed", started_ms=_now_ms(), message="exit code 3")
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            if browser._evaluate('document.getElementById("failed").className') == "box shown":
                break
            time.sleep(0.2)
        text = str(browser._evaluate("document.body.innerText"))
        assert "did not start" in text and "exit code 3" in text, text
        assert str(workspace / "logs") in text
        spinner = 'getComputedStyle(document.getElementById("spinner")).display'
        assert browser._evaluate(spinner) == "none"
    finally:
        browser.close()
