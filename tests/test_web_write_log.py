"""The record of write requests to Agent Web: what it holds, what it never holds, and that a
request never depends on it. A real server on a temp workspace; all values are fictional."""

from __future__ import annotations

import http.client
import json
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from bi_page_driver import BiPage, browser_missing
from test_host_wiring import ready

from host_runtime import write_log
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer

SECRET = "FICTIONAL-SECRET-73519"


@pytest.fixture
def served(tmp_path: Path) -> Iterator[tuple[AgentWebServer, Path]]:
    config, layout = ready(tmp_path)
    with build_runtime(config) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield server, layout.workspace_root / "logs" / write_log.FILE_NAME
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _send(
    server: AgentWebServer,
    method: str,
    path: str,
    *,
    body: bytes = b"{}",
    headers: dict[str, str] | None = None,
    token: bool = True,
) -> int:
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=30)
    sent = dict(headers or {})
    if token:
        sent["Authorization"] = f"Bearer {server.token}"
    connection.request(method, path, body=None if method == "GET" else body, headers=sent)
    response = connection.getresponse()
    response.read()
    connection.close()
    return response.status


def _lines(path: Path, wanted: int) -> list[dict[str, Any]]:
    deadline = time.monotonic() + 15
    found: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        if path.is_file():
            found = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
            if len(found) >= wanted:
                break
        time.sleep(0.02)
    return found


def test_a_write_is_one_line_and_a_read_none(served: tuple[AgentWebServer, Path]) -> None:
    server, log = served
    assert _send(server, "GET", "/api/activity") == 200
    status = _send(
        server,
        "POST",
        "/api/no-such-route",
        headers={"User-Agent": "fictional-ua/1", "X-AEP-Client": "fictional-driver"},
    )
    (line,) = _lines(log, 1)
    assert {k: line[k] for k in ("method", "path", "status", "client", "label", "user_agent")} == {
        "method": "POST",
        "path": "/api/no-such-route",
        "status": status,
        "client": "127.0.0.1",
        "label": "fictional-driver",
        "user_agent": "fictional-ua/1",
    }
    assert line["at"]


def test_no_token_or_secret_reaches_the_file(served: tuple[AgentWebServer, Path]) -> None:
    server, log = served
    _send(
        server,
        "POST",
        f"/api/no-such-route?token={SECRET}&q={SECRET}#{SECRET}",
        body=json.dumps({"secret": SECRET}).encode(),
        headers={
            "Cookie": f"session={SECRET}",
            "Referer": f"http://user:{SECRET}@127.0.0.1:1/page?token={SECRET}#token={SECRET}",
        },
    )
    (line,) = _lines(log, 1)
    assert line["path"] == "/api/no-such-route"
    assert line["referer"] == "http://127.0.0.1:1/page"
    held = log.read_text(encoding="utf-8")
    assert SECRET not in held and server.token not in held


def test_a_refused_write_and_a_method_nobody_serves_are_written(
    served: tuple[AgentWebServer, Path],
) -> None:
    server, log = served
    assert _send(server, "POST", "/api/activity", token=False) == 401
    for method in ("PUT", "PATCH", "DELETE"):
        assert _send(server, method, "/api/activity", body=b"") == 501  # unread: a reset
    assert [(x["method"], x["status"]) for x in _lines(log, 4)] == [
        ("POST", 401),
        ("PUT", 501),
        ("PATCH", 501),
        ("DELETE", 501),
    ]


def test_a_log_that_cannot_be_written_costs_no_request(
    served: tuple[AgentWebServer, Path],
) -> None:
    server, log = served
    log.parent.mkdir(parents=True, exist_ok=True)
    log.mkdir()  # a folder where the file should be
    assert _send(server, "POST", "/api/no-such-route") == 404
    assert _send(server, "GET", "/api/activity") == 200
    deadline = time.monotonic() + 10
    while not server.write_log.dropped and time.monotonic() < deadline:
        time.sleep(0.02)
    assert server.write_log.dropped == 1


def test_a_slow_log_does_not_slow_a_request(
    served: tuple[AgentWebServer, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    server, _log = served
    release = threading.Event()
    monkeypatch.setattr(server.write_log, "_write", lambda _batch: release.wait(20))
    started = time.monotonic()
    try:
        for _ in range(5):
            assert _send(server, "POST", "/api/no-such-route") == 404
        assert time.monotonic() - started < 5
    finally:
        release.set()


def test_concurrent_requests_leave_whole_lines(served: tuple[AgentWebServer, Path]) -> None:
    server, log = served

    def many(number: int) -> None:
        for each in range(10):
            _send(server, "POST", f"/api/no-such-route/{number}/{each}")

    threads = [threading.Thread(target=many, args=(n,)) for n in range(12)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    lines = _lines(log, 120)  # each parsed as JSON, so none is broken
    assert sorted(x["path"] for x in lines) == sorted(
        f"/api/no-such-route/{n}/{each}" for n in range(12) for each in range(10)
    )


def test_rotation_keeps_the_log_bounded(tmp_path: Path) -> None:
    log = write_log.WriteLog(tmp_path, max_bytes=2000, keep=2)
    for number in range(400):
        log.note(write_log.entry(method="POST", target=f"/x/{number}", status=200, user_agent="u",
                                 referer="", client="127.0.0.1", label=""))  # fmt: skip
    log.close()
    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [write_log.FILE_NAME, f"{write_log.FILE_NAME}.1", f"{write_log.FILE_NAME}.2"]
    assert all(p.stat().st_size <= 2000 for p in tmp_path.iterdir())


def test_rotation_works_a_line_at_a_time(tmp_path: Path) -> None:
    """How a host really writes: each request a batch of one."""
    log = write_log.WriteLog(tmp_path, max_bytes=1000, keep=2)
    for number in range(100):
        log._write([{"method": "POST", "path": f"/x/{number}", "pad": "x" * 60}])
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        write_log.FILE_NAME,
        f"{write_log.FILE_NAME}.1",
        f"{write_log.FILE_NAME}.2",
    ]
    assert all(p.stat().st_size <= 1000 for p in tmp_path.iterdir())
    newest = (tmp_path / write_log.FILE_NAME).read_text(encoding="utf-8").splitlines()
    assert json.loads(newest[-1])["path"] == "/x/99"


def test_a_full_queue_drops_and_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = write_log.WriteLog(tmp_path, queue_lines=1)
    monkeypatch.setattr(log, "_start", lambda: None)  # no writer: the queue stays full
    for _ in range(3):
        log.note({"method": "POST"})
    assert log.dropped == 2
    monkeypatch.undo()
    log.close()  # no thread was started
    log._write([{"method": "POST"}])
    held = (tmp_path / write_log.FILE_NAME).read_text(encoding="utf-8").splitlines()
    assert json.loads(held[-1]) == {"dropped": 2}


def test_a_line_cannot_be_split_or_made_long() -> None:
    line = write_log.entry(
        method="POST",
        target="/x",
        status=200,
        user_agent="a\nb" * 500,
        referer="not an address",
        client="127.0.0.1",
        label="c" * 900,
    )
    assert (
        len(line["user_agent"]) == write_log.MAX_TEXT and len(line["label"]) == write_log.MAX_TEXT
    )
    assert line["referer"] == ""
    assert "\n" not in json.dumps(line)
    assert write_log.clean_path(f"http://u:{SECRET}@h/x?y=1#z") == "/x"


def test_nothing_goes_to_the_console(
    served: tuple[AgentWebServer, Path], capfd: pytest.CaptureFixture[str]
) -> None:
    server, log = served
    _send(server, "POST", "/api/no-such-route")
    _lines(log, 1)
    captured = capfd.readouterr()
    assert "no-such-route" not in captured.err and "no-such-route" not in captured.out


@pytest.mark.skipif(browser_missing(), reason="no Chromium browser is installed")
def test_the_page_driver_names_itself(served: tuple[AgentWebServer, Path], tmp_path: Path) -> None:
    server, log = served
    address = f"http://127.0.0.1:{server.server_address[1]}/?token={server.token}"
    with BiPage(tmp_path / "browser", address) as page:
        page.run("fetch('/api/no-such-route', {method: 'POST', body: '{}'}).then(() => 1)")
        deadline = time.monotonic() + 15
        lines: list[dict[str, Any]] = []
        while not lines and time.monotonic() < deadline:
            lines = [x for x in _lines(log, 1) if x["path"] == "/api/no-such-route"]
    assert lines[0]["label"] == "tests/bi_page_driver"
    assert server.token not in log.read_text(encoding="utf-8")
