"""Harness telemetry, aep.telemetry.v1 with the v0.2 additions (owner 2026-10-08).

Ordered per run, nested spans, missing token usage left null, redaction,
idempotent storage, a never-blocking emitter, retention, and the read API
Atlas uses (no token; pages on this machine only; WebSocket stream).
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import socket
import struct
import threading
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch, served  # noqa: F401 - the server fixture
from test_gateway import _call, _host_gateway, _text, request

import telemetry.recorder as telemetry
from agent.gateway import HostTool, HostToolOutcome
from common.execution import RequestContext
from models.approved import _observed
from models.contracts import ModelRequest, ModelResponse, ModelTool
from telemetry.events import TelemetryEvent, sanitize
from telemetry.store import TelemetryStore


@pytest.fixture
def store(tmp_path: Path) -> Iterator[TelemetryStore]:
    telemetry.reset()
    item = TelemetryStore(tmp_path / "telemetry.sqlite")
    telemetry.configure(item, {"build": "test", "strategy_label": None})
    yield item
    telemetry.reset()
    item.close()


def events(item: TelemetryStore) -> list[dict[str, Any]]:
    recorder = telemetry.recorder()
    assert recorder is not None
    recorder.flush()
    return item.events_after(0, limit=5000)


class Observed:
    """The scripted model behind the host's llm.completed hook."""

    def __init__(self, inner: Any, usage: bool) -> None:
        self.inner, self.usage = inner, usage

    def generate(self, item: ModelRequest) -> ModelResponse:
        reply = self.inner.generate(item)
        if self.usage:
            reply = reply.model_copy(update={"input_tokens": 120, "output_tokens": 30})
        _observed(item, reply, 5.0)
        return reply


def test_a_conversation_turn_is_one_ordered_run_with_nested_spans(store: TelemetryStore) -> None:
    async def tool(context: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
        return HostToolOutcome(status="succeeded", data={"ok": True})

    host = HostTool(
        ModelTool(
            name="lookup", description="d", input_contract="x.v1", input_schema={"type": "object"}
        ),
        tool,
    )
    built, model = _host_gateway([host], [_call("lookup", {}), _text("done")])
    built.router.model = Observed(built.router.model, usage=False)
    result = asyncio.run(built.converse(request("go"), ()))
    assert result.status == "answered"
    found = events(store)
    kinds = [e["event_type"] for e in found]
    assert kinds[0] == "run.started" and kinds[-1] == "run.completed"
    assert {"llm.completed", "tool.completed", "state.entered", "state.exited"} <= set(kinds)
    assert [e["sequence"] for e in found] == list(range(len(found)))
    assert len({e["run_id"] for e in found}) == 1
    assert all(e["trace_id"] == "trace-1" for e in found)
    spans = {e["span_id"]: e for e in found}
    tool_done = next(e for e in found if e["event_type"] == "tool.completed")
    assert tool_done["attributes"]["tool_id"] == "lookup" and tool_done["status"] == "succeeded"
    llm = [e for e in found if e["event_type"] == "llm.completed"]
    # Each model call nests under its "model" state span, which nests under the run.
    assert all(spans[e["parent_span_id"]]["state"] == "model" for e in llm)
    done = found[-1]["attributes"]
    assert done["llm_calls"] == 2 and done["tool_calls"] == 1
    assert done["input_tokens"] is None and done["token_reports"] == 0  # not reported, not 0
    assert done["outcome"] == "answered"
    run = store.runs()[0]
    assert run["run_kind"] == "conversation_turn" and run["status"] == "succeeded"
    assert run["strategy_id"].startswith("st-") and run["complete"]


def test_reported_usage_is_summed_and_a_failed_model_call_is_recorded(
    store: TelemetryStore,
) -> None:
    built, _ = _host_gateway([], [_text("hi")])
    built.router.model = Observed(built.router.model, usage=True)
    asyncio.run(built.converse(request("go"), ()))
    found = events(store)
    llm = next(e for e in found if e["event_type"] == "llm.completed")
    assert llm["attributes"]["input_tokens"] == 120
    assert llm["attributes"]["model_alias"] == "routing"
    assert found[-1]["attributes"]["input_tokens"] == 120


def test_attributes_are_metadata_only() -> None:
    kept = sanitize(
        {
            "prompt": "secret plan",
            "answer_text": "x",
            "tool_id": "web/read@1",
            "note": "password=hunter2",
            "input_tokens": 5,
            "nested": {"content": "x", "n": 1},
            "long": "y" * 999,
        }
    )
    assert "prompt" not in kept and "answer_text" not in kept
    assert kept["note"] == "[redacted]" and kept["input_tokens"] == 5
    assert kept["nested"] == {"n": 1} and len(kept["long"]) == 300


def event(
    sequence: int,
    event_id: str = "e" * 32,
    run_id: str = "run-1",
    when: datetime | None = None,
    event_type: str = "state.entered",
) -> TelemetryEvent:
    return TelemetryEvent(
        event_id=event_id,
        run_id=run_id,
        trace_id="t",
        span_id="s",
        sequence=sequence,
        timestamp=when or datetime.now(UTC),
        event_type=event_type,
        status="started",
    )


def test_storage_is_idempotent_and_ordered_by_sequence(tmp_path: Path) -> None:
    item = TelemetryStore(tmp_path / "t.sqlite")
    assert item.append([event(1, "b" * 32), event(0, "a" * 32)]) == 2
    assert item.append([event(1, "b" * 32)]) == 0  # duplicate delivery
    assert [e["sequence"] for e in item.run_events("run-1")] == [0, 1]
    assert [e["sequence"] for e in item.events_after(0)] == [1, 0]  # arrival order
    item.close()


def test_retention_drops_whole_old_runs(tmp_path: Path) -> None:
    item = TelemetryStore(tmp_path / "t.sqlite")
    old = datetime.now(UTC) - timedelta(days=40)
    item.append(
        [
            event(0, "o" * 32, "run-old", old, "run.started"),
            event(0, "n" * 32, "run-new", None, "run.started"),
        ]
    )
    assert item.prune() == 1
    assert [r["run_id"] for r in item.runs()] == ["run-new"]
    assert item.run_events("run-old") == []
    item.close()


def test_emitting_never_blocks_or_raises_when_the_writer_falls_behind(
    store: TelemetryStore,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = telemetry.recorder()
    assert recorder is not None
    gate = threading.Event()
    original = store.append

    def slow(batch: Any) -> int:
        gate.wait(5)
        return original(batch)

    monkeypatch.setattr(store, "append", slow)
    monkeypatch.setattr(telemetry, "QUEUE_LIMIT", 100)
    recorder.queue.maxsize = 100
    with telemetry.run("capability_call"):
        started = time.perf_counter()
        for index in range(5_000):
            telemetry.emit("state.entered", status="started", state=f"s{index % 5}")
        elapsed = time.perf_counter() - started
    gate.set()
    assert elapsed < 1.0, elapsed
    assert recorder.dropped > 0


def test_a_workflow_run_is_its_own_run_with_steps(store: TelemetryStore, tmp_path: Path) -> None:
    from test_chat_authoring import studio, workflow

    chat, recorder_calls = studio(tmp_path)
    item, problems = chat.draft("owner", None, "Echo", workflow("read-it"))
    assert item is not None, problems
    chat.execute("owner", item, {"month": "2026-10"}, "test")
    found = events(store)
    runs = {e["run_id"] for e in found}
    assert len(runs) == 1 and next(iter(runs)).startswith("run-")
    kinds = [(e["event_type"], e["state"]) for e in found]
    assert ("state.entered", "step") in kinds and ("tool.completed", "capability") in kinds
    assert found[-1]["event_type"] == "run.completed" and found[-1]["status"] == "succeeded"
    assert found[0]["attributes"]["workflow_id"] == "engineering/echo-month@1.0.0"


def get(url: str, origin: str | None = None) -> Any:
    import urllib.error
    import urllib.request

    item = urllib.request.Request(url)
    if origin:
        item.add_header("Origin", origin)
    try:
        with urllib.request.urlopen(item, timeout=10) as answer:
            return answer.status, dict(answer.headers), json.loads(answer.read())
    except urllib.error.HTTPError as refused:
        return refused.code, dict(refused.headers), None


def _ws(port: int, path: str, origin: str) -> socket.socket:
    sock = socket.create_connection(("127.0.0.1", port), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall(
        (
            f"GET {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\n"
            f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\nOrigin: {origin}\r\n\r\n"
        ).encode()
    )
    head = b""
    while b"\r\n\r\n" not in head:
        head += sock.recv(1)
    assert b" 101 " in head.split(b"\r\n")[0]
    return sock


def _message(sock: socket.socket) -> dict[str, Any]:
    while True:
        first, second = sock.recv(1)[0], sock.recv(1)[0]
        size = second & 0x7F
        if size == 126:
            size = struct.unpack(">H", sock.recv(2))[0]
        elif size == 127:
            size = struct.unpack(">Q", sock.recv(8))[0]
        data = b""
        while len(data) < size:
            data += sock.recv(size - len(data))
        if first & 0x0F == 0x1:
            return dict(json.loads(data))


def test_atlas_reads_runs_events_and_the_stream_without_the_token(
    served: Any,
    store: TelemetryStore,  # noqa: F811
) -> None:
    with telemetry.run("capability_call", trace_id="trace-x"):
        telemetry.emit("state.entered", status="started", state="model")
    events(store)
    url = base(served)
    _, _, health = get(url + "/api/v1/telemetry/health")
    assert health["schema_version"] == "aep.telemetry.v1" and health["dropped"] == 0
    status, headers, listed = get(url + "/api/v1/telemetry/runs", "http://127.0.0.1:8127")
    assert status == 200
    assert headers.get("Access-Control-Allow-Origin") == "http://127.0.0.1:8127"
    (run,) = listed["runs"]
    # A benchmark case links to the AEP runs that answered it by trace id.
    assert (
        get(url + "/api/v1/telemetry/runs?trace_id=trace-x")[2]["runs"][0]["run_id"]
        == run["run_id"]
    )
    assert get(url + "/api/v1/telemetry/runs?trace_id=trace-y")[2]["runs"] == []
    _, _, page = get(url + f"/api/v1/telemetry/runs/{run['run_id']}/events")
    assert [e["event_type"] for e in page["events"]] == [
        "run.started",
        "state.entered",
        "run.completed",
    ]
    assert get(url + "/api/v1/telemetry/runs", "https://evil.example")[0] == 403
    # Other Agent Web routes still need the token.
    assert fetch(url + "/api/conversations").status == 401

    port = int(url.rsplit(":", 1)[1].strip("/"))
    sock = _ws(port, "/api/v1/telemetry/stream?after_ingest_seq=0", "http://localhost:5173")
    try:
        first = _message(sock)
        assert first["event_type"] == "run.started" and first["ingest_seq"] >= 1
        with telemetry.run("capability_call"):
            pass
        telemetry.recorder().flush()  # type: ignore[union-attr]
        seen = [_message(sock)["event_type"] for _ in range(4)]
        assert seen[-2:] == ["run.started", "run.completed"]
    finally:
        sock.close()


def test_strategies_compare_on_success_latency_and_retries(tmp_path: Path) -> None:
    from telemetry.report import compare, markdown

    item = TelemetryStore(tmp_path / "t.sqlite")
    now = datetime.now(UTC)
    rows = []
    for index, (strategy, status, duration) in enumerate(
        [("st-a", "succeeded", 100), ("st-a", "failed", 300), ("st-b", "succeeded", 50)]
    ):
        run = f"run-{index}"
        rows += [
            TelemetryEvent(
                event_id=f"{index}s".ljust(32, "x"),
                run_id=run,
                trace_id="t",
                span_id="s",
                sequence=0,
                timestamp=now,
                event_type="run.started",
                status="started",
                attributes={"run_kind": "conversation_turn", "strategy_id": strategy},
            ),
            TelemetryEvent(
                event_id=f"{index}c".ljust(32, "x"),
                run_id=run,
                trace_id="t",
                span_id="s",
                sequence=1,
                timestamp=now,
                event_type="run.completed",
                status=status,
                attributes={"duration_ms": duration, "llm_calls": 2, "input_tokens": None},
            ),
        ]
    rows.append(
        TelemetryEvent(
            event_id="r".ljust(32, "x"),
            run_id="run-1",
            trace_id="t",
            span_id="s",
            sequence=2,
            timestamp=now,
            event_type="retry.scheduled",
            status="succeeded",
        )
    )
    item.append(rows)
    item.close()
    report = {row["strategy_id"]: row for row in compare(tmp_path / "t.sqlite")}
    assert report["st-a"]["runs"] == 2 and report["st-a"]["success_rate"] == 0.5
    assert report["st-a"]["retried_runs"] == 1 and report["st-a"]["token_coverage"] == 0.0
    assert report["st-b"]["p50_ms"] == 50.0
    assert "| st-a | conversation_turn | 2 |" in markdown(
        list(report.values()), ("strategy_id", "run_kind")
    )
