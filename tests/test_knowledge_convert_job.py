"""Convert runs in the background, one original at a time (owner, 2026-10-13)."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from test_agent_web import base, fetch
from test_knowledge_pipeline_web import _step, served_pipeline  # noqa: F401 - fixture

from host_runtime.knowledge_convert import ConvertedItem, ConvertRun, run_convert
from host_runtime.web import AgentWebServer
from host_runtime.web_page import PAGE


def _run(*paths: str) -> ConvertRun:
    return ConvertRun(run_id="convert-1", sandbox_id="sb-1", mode="apply", paths=paths,
                      progress_key="cvkey000001", started="2026-10-13T00:00:00+00:00")


def test_each_original_is_converted_alone_and_a_stop_ends_the_run() -> None:
    seen: list[tuple[str, ...]] = []
    stop = threading.Event()

    def convert(box: str, chosen: tuple[str, ...], mode: str, key: str) -> Any:
        seen.append(chosen)
        stop.set()  # the person presses Stop while the first original runs
        if chosen == ("drop/b.pdf",):
            raise OSError("disk")
        return SimpleNamespace(items=[ConvertedItem(path=chosen[0], status="written")])

    states: list[str] = []
    done = run_convert(convert, _run("drop/a.pdf", "drop/b.pdf"), stop,
                       lambda run: states.append(run.status))
    assert seen == [("drop/a.pdf",)] and done.status == "stopped"
    finished = run_convert(convert, _run("drop/b.pdf"), threading.Event(), lambda run: None)
    assert finished.status == "finished" and finished.items[0].status == "OSError"


def test_the_page_runs_convert_in_the_background(
    served_pipeline: tuple[AgentWebServer, Path],  # noqa: F811 - fixture
) -> None:
    server, _ = served_pipeline
    url = base(server) + "/api/knowledge/convert"
    made = _step(server, "sandbox-create", {"base": "k-test", "label": "cv"})
    sandbox = made["data"]["sandbox_id"]
    empty = json.loads(fetch(url + "/start", token=server.token,
                             body={"sandbox_id": sandbox, "mode": "apply"}).body)
    assert empty == {"ok": False, "code": "drop_empty"}
    assert _step(server, "drop-add", {"sandbox_id": sandbox, "name": "a.txt",
                                      "data_base64": "aGVsbG8K"})["ok"]
    assert fetch(url + "/start", body={"sandbox_id": sandbox, "mode": "apply"}).status == 401
    assert json.loads(fetch(url + "/start", token=server.token,
                            body={"sandbox_id": sandbox, "mode": "apply"}).body)["ok"]
    deadline = time.monotonic() + 30
    while True:
        run = json.loads(fetch(f"{url}?sandbox_id={sandbox}", token=server.token).body)["run"]
        if run["status"] == "finished" or time.monotonic() > deadline:
            break
        time.sleep(0.2)
    assert run["status"] == "finished"
    assert [(i["path"], i["status"]) for i in run["items"]] == [("drop/a.txt", "written")]
    assert run["progress"]["phase"] == "converting"
    for hook in ('id="kp-convert-stop"', 'id="kp-convert-bar"', "/api/knowledge/convert/start",
                 'id="kp-status-time"'):
        assert hook in PAGE
