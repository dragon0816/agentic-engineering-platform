"""The opt-in browser diagnostics switch (`AEP_BROWSER_DIAG_DIR`).

CI 2026-10-20: tabs vanished on the hosted runner with nothing to say why.
The switch records the browser's own log and the DevTools endpoints on a
failure; unset, the browser is launched and fails exactly as before.
"""

import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from integrations.browser import DIAG_DIR_ENV, Browser, BrowserError

LOGGING = ("--enable-logging=stderr", "--v=0")


def launched(monkeypatch: pytest.MonkeyPatch, browser: Browser) -> dict[str, Any]:
    """Launch with a stand-in for the process; return what Popen was given."""
    seen: dict[str, Any] = {}

    class Process:
        def __init__(self, arguments: list[str], **kwargs: Any) -> None:
            seen["arguments"] = arguments
            seen.update(kwargs)

    monkeypatch.setattr(subprocess, "Popen", Process)
    monkeypatch.setattr(browser, "_published_port", lambda: 4711)
    browser._launch()
    return seen


def no_page(browser: Browser) -> None:
    browser._targets = lambda port=None: []  # type: ignore[method-assign]
    with pytest.raises(BrowserError) as refused:
        browser.page(within_s=0)
    assert refused.value.code == "no_page"


def test_unset_changes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DIAG_DIR_ENV, raising=False)
    monkeypatch.chdir(tmp_path)
    browser = Browser(tmp_path / "profile", executable="msedge.exe")
    arguments = browser._arguments()
    assert not set(LOGGING) & set(arguments)
    assert arguments[-1] == "about:blank"
    seen = launched(monkeypatch, browser)
    assert seen["stderr"] is subprocess.DEVNULL
    assert seen["stdout"] is subprocess.DEVNULL
    assert seen["arguments"] == arguments

    def nothing_fetched(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("diagnostics fetched an endpoint while switched off")

    monkeypatch.setattr(urllib.request, "urlopen", nothing_fetched)
    no_page(browser)
    # Nothing was written here: no log, no record (the working directory too).
    assert list(tmp_path.iterdir()) == []


def test_an_empty_value_is_the_same_as_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(DIAG_DIR_ENV, "  ")
    browser = Browser(tmp_path / "profile", executable="msedge.exe")
    assert not set(LOGGING) & set(browser._arguments())
    assert launched(monkeypatch, browser)["stderr"] is subprocess.DEVNULL


def test_set_logs_stderr_and_records_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diag = tmp_path / "diag"
    monkeypatch.setenv(DIAG_DIR_ENV, str(diag))
    browser = Browser(tmp_path / "profile", executable="msedge.exe")
    arguments = browser._arguments()
    assert arguments[-3:] == [*LOGGING, "about:blank"]
    seen = launched(monkeypatch, browser)
    handle = seen["stderr"]
    assert handle is not subprocess.DEVNULL
    logs = list(diag.glob("*.stderr.log"))
    assert len(logs) == 1 and Path(handle.name) == logs[0]

    answers = {
        "/json/version": {"Browser": "Edg/999.0.0.0", "Protocol-Version": "1.3"},
        "/json/list": [
            {"type": "page", "url": "edge://newtab/", "title": "secret page title"},
            {"type": "background_page", "url": "chrome-extension://x/bg.html"},
        ],
    }

    def endpoint(path: str) -> Any:
        return answers[path]

    browser._diag_endpoint = endpoint  # type: ignore[method-assign]
    no_page(browser)
    (record_path,) = diag.glob("*-no_page.json")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["code"] == "no_page" and record["port"] == 4711
    assert record["version"]["Browser"] == "Edg/999.0.0.0"
    # Types and addresses only: a title is page content and is not kept.
    assert record["targets"] == [
        {"type": "page", "url": "edge://newtab/"},
        {"type": "background_page", "url": "chrome-extension://x/bg.html"},
    ]
    assert "secret page title" not in record_path.read_text(encoding="utf-8")

    browser._port = None
    browser._process = None
    browser.close()
    assert handle.closed
    assert json.loads(logs[0].read_text(encoding="utf-8").splitlines()[0])["arguments"] == (
        arguments
    )


def test_a_navigation_failure_is_recorded_and_still_raised(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diag = tmp_path / "diag"
    monkeypatch.setenv(DIAG_DIR_ENV, str(diag))
    browser = Browser(tmp_path / "profile", executable="msedge.exe")

    class Tab:
        def call(self, method: str, **params: Any) -> dict[str, Any]:
            return {"errorText": "net::ERR_CONNECTION_REFUSED"}

    browser._page = Tab()  # type: ignore[assignment]
    # The browser is gone: the endpoints answer with why there was nothing.
    with pytest.raises(BrowserError) as refused:
        browser.navigate("http://127.0.0.1:9/", settle_s=0)
    assert refused.value.code == "navigation_failed"
    (record_path,) = diag.glob("*-navigation_failed.json")
    record = json.loads(record_path.read_text(encoding="utf-8"))
    assert record["detail"] == "net::ERR_CONNECTION_REFUSED"
    assert record["version"] == {"unavailable": "no port"}
