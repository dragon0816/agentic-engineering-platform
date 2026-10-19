"""Telegram's one status message for a running turn (owner 2026-10-19).
Fakes only: no Bot API, no model, no network."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Mapping
from itertools import pairwise
from pathlib import Path
from typing import Any

from test_telegram_ingress import (
    OWNER,
    STATUS_MARK,
    FakeReply,
    FakeTransport,
    ingress,
    poll,
    update,
)
from test_telegram_turn_limits import Scripted

from agent.turn_progress import TurnProgress
from models.contracts import ModelResponse, ModelToolCall


def _text(text: str) -> ModelResponse:
    from common.execution import TraceIdentifiers

    return ModelResponse(
        trace=TraceIdentifiers(trace_id="x", request_id="x", span_id="x"),
        model_alias="routing",
        text=text,
    )


def _status_sends(transport: FakeTransport) -> list[str]:
    return [
        payload["text"]
        for url, payload in transport.calls
        if url.endswith("/sendMessage") and payload["text"].startswith(STATUS_MARK)
    ]


def test_a_long_turn_edits_one_status_message_a_few_times(tmp_path: Path) -> None:
    """Twenty tool events in a burst become one status message and a bounded
    number of edits, all of the same message: never a stream of messages."""

    def script(n: int) -> ModelResponse | list[ModelToolCall]:
        if n > 10:
            return _text("All ten checks ran.")
        return [
            ModelToolCall(call_id=f"a{n}", name="shipment__run", arguments={}),
            ModelToolCall(call_id=f"b{n}", name="admin__probe", arguments={"n": n}),
        ]

    transport = FakeTransport([[update(1, OWNER, "run the checks ten times")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.router.model = Scripted(script)
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered" and delivery.replied
    assert transport.sent() == ["All ten checks ran."]
    assert len(_status_sends(transport)) == 1
    edits = [payload for url, payload in transport.calls if url.endswith("/editMessageText")]
    assert edits and {payload["message_id"] for payload in edits} == {1}
    # The first edit is immediate; later ones wait for the refresh period, and
    # the burst took far less than one: the first edit and the final one.
    assert len(edits) <= 3, [payload["text"] for payload in edits]
    statuses = transport.statuses()
    assert any("工具 " in text and "/150" in text and "/ 30:00" in text for text in statuses)
    assert statuses[-1].startswith("✅ Done after")
    assert all("run the checks" not in text for text in statuses)


# -- the status message follows every change, at most one edit per window --------
# (owner 2026-10-19: "狀態有變就發", without flooding the chat)

STAGES = ("collect_context", "execute", "validate")


class TimedTransport(FakeTransport):
    """Records when each status edit arrives; can answer edits with a 429."""

    def __init__(self, limited: list[float] | None = None) -> None:
        super().__init__([])
        self.limited = list(limited or [])
        self.edits: list[tuple[float, str, int]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> FakeReply:
        if url.endswith("/editMessageText"):
            payload = json.loads(body)
            self.calls.append((url, payload))
            if self.limited:
                retry = self.limited.pop(0)
                self.edits.append((time.monotonic(), payload["text"], 429))
                return FakeReply(429, {"ok": False, "parameters": {"retry_after": retry}})
            self.edits.append((time.monotonic(), payload["text"], 200))
            return FakeReply(200, {"ok": True, "result": True})
        return super().send(url, body, headers, timeout_s)

    def delivered(self) -> list[tuple[float, str]]:
        return [(at, text) for at, text, status in self.edits if status == 200]


def _drive(
    tmp_path: Path,
    transport: TimedTransport,
    steps: Any,
    *,
    interval: float,
) -> None:
    """Open one status message, let `steps(turn, progress)` change the turn,
    then finish it as answered."""
    item, _, _ = ingress(tmp_path, transport)
    item.status_edit_interval_s = interval
    item.progress_refresh_s = 60.0  # the clock refresh stays out of these tests

    async def main() -> None:
        turn = TurnProgress(turn_id="t")
        progress = await item._progress(42, "Working on it", turn)
        await steps(turn, progress)
        await progress.finish(True)

    asyncio.run(main())


def _status_messages(transport: FakeTransport) -> int:
    return len(_status_sends(transport))


def test_each_change_edits_the_one_status_message(tmp_path: Path) -> None:
    """Changes further apart than the window each produce their own edit,
    showing that change; the status message is sent once."""

    async def steps(turn: TurnProgress, _progress: object) -> None:
        turn.set_limits(150, 1800)
        await asyncio.sleep(0.25)
        turn.harness_phase("knowledge", STAGES, "collecting", 0)
        await asyncio.sleep(0.25)
        turn.tool_started("knowledge__ask")
        await asyncio.sleep(0.25)
        turn.harness_phase("knowledge", STAGES, "collecting", 1)
        await asyncio.sleep(0.25)

    transport = TimedTransport()
    _drive(tmp_path, transport, steps, interval=0.1)
    texts = [text for _, text in transport.delivered()]
    assert _status_messages(transport) == 1
    assert any("工具 0/150" in text for text in texts)
    assert any("Knowledge：① 規劃 ✓ ② 查資料…" in text for text in texts)
    assert any("工具 1/150" in text for text in texts)
    assert any("查資料（第 2 輪）…" in text for text in texts)
    assert texts[-1].startswith("✅ Done after")
    assert {payload["message_id"] for url, payload in transport.calls if "edit" in url} == {1}


def test_a_burst_is_coalesced_and_the_latest_state_is_shown(tmp_path: Path) -> None:
    """Thirty changes in a quick burst: at most one edit per window, and the
    edit after the burst shows the last state, not a dropped earlier one."""
    interval = 0.3

    async def steps(turn: TurnProgress, _progress: object) -> None:
        turn.set_limits(150, 1800)
        for n in range(30):
            turn.tool_started(f"probe_{n}")
            turn.tool_finished(f"probe_{n}", "succeeded")
            await asyncio.sleep(0.02)
        # Let the window that holds the burst's tail close before finishing.
        await asyncio.sleep(interval + 0.15)

    transport = TimedTransport()
    _drive(tmp_path, transport, steps, interval=interval)
    delivered = transport.delivered()
    running = [(at, text) for at, text in delivered if not text.startswith("✅")]
    gaps = [later - earlier for (earlier, _), (later, _) in pairwise(delivered)]
    assert all(gap >= interval - 0.05 for gap in gaps), gaps
    # 0.6 s of changes with a 0.3 s window: a handful of edits, not thirty.
    assert 2 <= len(running) <= 5, [text for _, text in running]
    assert "工具 30/150" in running[-1][1]
    assert _status_messages(transport) == 1


def test_an_unchanged_state_sends_no_edit(tmp_path: Path) -> None:
    async def steps(turn: TurnProgress, progress: Any) -> None:
        turn.set_limits(150, 1800)
        await asyncio.sleep(0.15)
        for _ in range(5):
            turn.set_limits(150, 1800)  # the same state again
            progress.changed()
            await asyncio.sleep(0.1)

    transport = TimedTransport()
    _drive(tmp_path, transport, steps, interval=0.05)
    running = [text for _, text in transport.delivered() if not text.startswith("✅")]
    assert len(running) == 1, running
    assert len(set(running)) == len(running)


def test_a_rate_limit_is_waited_out_and_then_the_latest_state_shown(tmp_path: Path) -> None:
    retry = 0.6

    async def steps(turn: TurnProgress, _progress: object) -> None:
        turn.set_limits(150, 1800)  # its edit gets a 429
        await asyncio.sleep(0.1)
        turn.tool_started("admin__probe")
        await asyncio.sleep(0.1)
        turn.tool_finished("admin__probe", "succeeded")
        await asyncio.sleep(retry + 0.3)

    transport = TimedTransport(limited=[retry])
    _drive(tmp_path, transport, steps, interval=0.05)
    limited_at = next(at for at, _, status in transport.edits if status == 429)
    after = transport.delivered()
    assert after and after[0][0] - limited_at >= retry - 0.05
    assert "工具 1/150" in after[0][1]
    assert after[-1][1].startswith("✅ Done after")
    assert _status_messages(transport) == 1


def test_a_harness_phase_from_a_worker_thread_edits_the_message(tmp_path: Path) -> None:
    """A Harness inside a tool may run in a worker thread (asyncio.to_thread):
    its phase still reaches the status message."""

    async def steps(turn: TurnProgress, _progress: object) -> None:
        await asyncio.to_thread(turn.harness_phase, "workflow", ("execute",), "executing", 0)
        await asyncio.sleep(0.2)

    transport = TimedTransport()
    _drive(tmp_path, transport, steps, interval=0.05)
    assert any("Workflow：① 規劃 ✓ ② 執行…" in text for _, text in transport.delivered())
