"""A conversation turn on the shared Harness (unification U4, owner 2026-10-09):
the Host checks the answer against the turn's real tool results and files."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from test_gateway import _call, _host_gateway, _text, request

from agent.conversation_harness import check_answer, named_files
from agent.gateway import HostTool, HostToolOutcome
from common.execution import RequestContext
from models.contracts import ModelTool


def tool(status: str = "succeeded") -> HostTool:
    async def run(context: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
        return HostToolOutcome(status=status, data={})  # type: ignore[arg-type]

    return HostTool(
        ModelTool(
            name="make", description="d", input_contract="x.v1", input_schema={"type": "object"}
        ),
        run,
    )


def test_a_claimed_action_without_a_tool_gets_one_retry_with_the_reason() -> None:
    built, model = _host_gateway(
        [], [_text("我已經產生報表檔案了。"), _text("我還沒有執行任何工具。")]
    )
    result = asyncio.run(built.converse(request("做報表"), ()))
    assert result.text == "我還沒有執行任何工具。"
    assert len(model.calls) == 2
    feedback = model.calls[1].messages[-1].text
    assert feedback.startswith("[Host check failed]") and "no tool call succeeded" in feedback


def test_a_claim_backed_by_a_successful_tool_needs_no_retry() -> None:
    built, model = _host_gateway([tool()], [_call("make", {}), _text("已產生報表。")])
    result = asyncio.run(built.converse(request("做報表"), ()))
    assert result.text == "已產生報表。" and len(model.calls) == 2


def test_a_named_output_that_is_missing_or_empty_is_caught(tmp_path: Path) -> None:
    root = tmp_path / "tasks"
    (root / "out").mkdir(parents=True)
    (root / "out" / "empty.csv").write_text("", encoding="utf-8")
    report = root / "out" / "report.xlsx"
    built, model = _host_gateway(
        [tool()], [_call("make", {}), _text(f"已寫入 {report}。"), _text(f"再次確認：{report}。")]
    )
    built._workspace_roots = (str(root),)
    result = asyncio.run(built.converse(request("做報表"), ()))
    assert len(model.calls) == 3  # one retry, then the Host's note
    assert "Host 檢查未通過" in result.text and "does not exist" in result.text
    checks, reasons = check_answer(f"結果在 {root / 'out' / 'empty.csv'}", (), (str(root),))
    assert [c.status for c in checks] == ["passed", "failed"] and "is empty" in reasons[0]


def test_paths_outside_the_task_folders_and_plain_answers_are_not_checked(tmp_path: Path) -> None:
    root = tmp_path / "tasks"
    assert named_files(r"see C:\Windows\notepad.exe and docs", (str(root),)) == []
    built, model = _host_gateway([], [_text("請問要哪一個月份？")])
    result = asyncio.run(built.converse(request("做報表"), ()))
    assert result.text == "請問要哪一個月份？" and len(model.calls) == 1
