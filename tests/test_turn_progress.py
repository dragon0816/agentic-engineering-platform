"""The live, content-free progress of a running turn (owner 2026-10-19):
what the Gateway tool loop and the shared Harness runner report. Fakes only."""

import json
from typing import Any

from test_conversation_turn_guards import (
    ANSWER_TEXT,
    SECRET_ARGUMENT,
    FakeClock,
    _built,
    _calls,
    _converse,
    _tool,
    _working,
)
from test_gateway import _text

from agent import turn_progress
from agent.harness_plan import build_plan
from agent.harness_run import HarnessCheckResult
from agent.harness_runner import run_harness
from agent.skills import SkillHarnessGuidance
from agent.turn_progress import TURN_PROGRESS, TurnProgress, TurnProgressBoard, compact_lines
from common.assets import AssetIdentity


def test_the_turn_reports_tool_progress_with_names_counts_and_no_content() -> None:
    tool, _ = _tool("files__read", _working)
    built, _ = _built(
        lambda n: (
            _calls(("files__read", {"path": SECRET_ARGUMENT}))
            if n == 1
            else _calls(("files__read", {"path": "other"}))
            if n == 2
            else _text(ANSWER_TEXT)
        ),
        tool,
    )
    progress = TurnProgress(turn_id="t1", session_id="s1", owner="me")
    token = TURN_PROGRESS.set(progress)
    try:
        result = _converse(built)
    finally:
        TURN_PROGRESS.reset(token)
    assert result.status == "answered"
    snapshot = progress.snapshot()
    assert snapshot["tool_count"] == 2 and snapshot["tool_cap"] == 150
    assert snapshot["time_limit_s"] == 1800
    assert [tool["name"] for tool in snapshot["tools"]] == ["files__read", "files__read"]
    assert {tool["status"] for tool in snapshot["tools"]} == {"succeeded"}
    dumped = json.dumps(snapshot, ensure_ascii=False)
    assert SECRET_ARGUMENT not in dumped and ANSWER_TEXT not in dumped
    # The conversation's own Host check ran as a Harness and was shown.
    assert snapshot["harness"]["domain"] == "conversation"
    assert snapshot["harness"]["done"] is True


class _Actions:
    def __init__(self, fail_first: bool) -> None:
        self.fail_first = fail_first
        self.validations = 0
        self.seen: list[dict[str, Any] | None] = []

    def _look(self) -> None:
        progress = turn_progress.current()
        self.seen.append(None if progress is None else progress.snapshot()["harness"])

    def collect_context(self) -> str:
        self._look()
        return "context"

    def execute(self) -> str:
        self._look()
        return "executed"

    def validate(self) -> tuple[HarnessCheckResult, ...]:
        self._look()
        self.validations += 1
        status: Any = "failed" if self.fail_first and self.validations == 1 else "passed"
        return (HarnessCheckResult(check_id="cited", status=status, evidence_ref="e"),)


def _knowledge_plan() -> Any:
    return build_plan(
        task_id="t",
        task_sha256="0" * 64,
        domain="knowledge",
        skill=AssetIdentity(namespace="n", name="k", version="1.0.0"),
        guidance=SkillHarnessGuidance(domains=("knowledge",), fallback="retry", max_retries=1),
        host_checks=("cited",),
        max_retries=1,
    )


def test_harness_phases_and_retries_are_reported_by_their_names() -> None:
    progress = TurnProgress(turn_id="t1", session_id="s1", owner="me")
    actions = _Actions(fail_first=True)
    token = TURN_PROGRESS.set(progress)
    try:
        run = run_harness(_knowledge_plan(), actions)
    finally:
        TURN_PROGRESS.reset(token)
    assert run.phase == "validated"
    phases = [(seen or {}).get("phase") for seen in actions.seen]
    assert phases == ["collecting", "executing", "validating"] * 2
    second_collect = actions.seen[3]
    assert second_collect is not None and second_collect["retry"] == 1
    states = {step["stage"]: step["state"] for step in second_collect["steps"]}
    assert states == {
        "plan": "done",
        "collect_context": "active",
        "execute": "waiting",
        "validate": "waiting",
    }
    final = progress.snapshot()["harness"]
    assert final["done"] is True and final["phase"] == "validated"
    assert "Knowledge" in compact_lines(progress.snapshot())[0]


def test_compact_lines_show_the_stepper_the_count_and_the_time() -> None:
    clock = FakeClock()
    progress = TurnProgress(turn_id="t", clock=clock, tool_cap=150, time_limit_s=1800)
    progress.harness_phase("knowledge", ("collect_context", "execute", "validate"), "collecting", 1)
    for _ in range(12):
        progress.tool_started("files__read")
    clock.now += 185
    lines = compact_lines(progress.snapshot())
    assert lines[0] == "Knowledge：① 規劃 ✓ ② 查資料（第 2 輪）… ③ 執行 ④ 驗收"
    assert lines[1] == "工具 12/150 · 3:05 / 30:00"


def test_the_board_serves_only_the_owner_and_forgets_a_finished_turn() -> None:
    board = TurnProgressBoard()
    mine = board.begin(TurnProgress(turn_id="t1", session_id="s1", owner="me"))
    board.begin(TurnProgress(turn_id="t2", session_id="s2", owner="me"))
    shown = board.read("s1", "me")
    assert shown is not None and shown["turn_id"] == "t1"
    assert board.read("s1", "someone-else") is None
    assert board.read("s3", "me") is None
    board.end(mine)
    assert board.read("s1", "me") is None and board.read("s2", "me") is not None
