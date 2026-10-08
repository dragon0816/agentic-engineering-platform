"""One-click Agent Web (owner 2026-10-08): the running server's address is kept
in the workspace, and `open` starts the server when nothing answers."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import pytest

from host_runtime.launcher import (
    LauncherError,
    clear_record,
    console_python,
    open_agent,
    read_record,
    record_path,
    refreshed_environment,
    write_record,
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
    tmp_path: Path, server: ThreadingHTTPServer,
) -> None:
    write_record(tmp_path, address(server), server.server_address[1])
    opened: list[str] = []

    def never() -> None:
        raise AssertionError("must not start a second server")

    assert open_agent(tmp_path, tmp_path / "host.json", start=never,
                      opener=opened.append) == "opened"
    assert opened == [address(server)]


def test_a_stale_record_is_dropped_and_the_server_started_then_opened(
    tmp_path: Path, server: ThreadingHTTPServer,
) -> None:
    write_record(tmp_path, address(server, "old-token"), 1)  # from a server that died
    opened: list[str] = []
    started: list[bool] = []

    def start() -> None:
        started.append(True)
        write_record(tmp_path, address(server), server.server_address[1])

    assert open_agent(tmp_path, tmp_path / "host.json", start=start, opener=opened.append,
                      poll=0.01) == "started"
    assert started == [True] and opened == [address(server)]


def test_a_server_that_never_answers_is_reported_with_where_to_look(tmp_path: Path) -> None:
    with pytest.raises(LauncherError) as failed:
        open_agent(tmp_path, tmp_path / "host.json", start=lambda: None, opener=print,
                   wait_seconds=0.05, poll=0.01)
    assert failed.value.code == "agent_web_not_started" and "logs" in str(failed.value)


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
