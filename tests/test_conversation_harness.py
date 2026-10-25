"""A conversation turn on the shared Harness (unification U4, owner 2026-10-09):
the Host checks the answer against the turn's real tool results and files."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from test_gateway import _call, _cut, _host_gateway, _text, request

from agent.conversation_harness import CLAIM_NOTE, check_answer, named_files
from agent.gateway import HostTool, HostToolOutcome
from common.execution import RequestContext
from models.contracts import ModelMessage, ModelTool


def tool(status: str = "succeeded") -> HostTool:
    async def run(context: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
        return HostToolOutcome(status=status, data={})

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
    assert "（系統檢查：回答提到的檔案不存在或是空的：" in result.text
    assert "report.xlsx（不存在）" in result.text and "does not exist" not in result.text
    checks, reasons = check_answer(f"結果在 {root / 'out' / 'empty.csv'}", (), (str(root),))
    assert [c.status for c in checks] == ["passed", "failed"] and "is empty" in reasons[0]


def test_paths_outside_the_task_folders_and_plain_answers_are_not_checked(tmp_path: Path) -> None:
    root = tmp_path / "tasks"
    assert named_files(r"see C:\Windows\notepad.exe and docs", (str(root),)) == []
    built, model = _host_gateway([], [_text("請問要哪一個月份？")])
    result = asyncio.run(built.converse(request("做報表"), ()))
    assert result.text == "請問要哪一個月份？" and len(model.calls) == 1


CARD = "data:image/png;base64,iVBORw0KGgo="


def test_the_retry_keeps_the_picture_on_the_persons_message() -> None:
    """Live test 2026-10-20: a business-card photo plus an unbacked "stored" claim
    failed with conversation_history_invalid, because the retry appended the
    answer and the Host note after the message that carries the picture."""
    built, model = _host_gateway(
        [], [_text("名片已經儲存到資料庫了。"), _text("名片內容：王小明。我沒有儲存它。")]
    )
    history = (ModelMessage(role="user", text="請解析這張名片並存進名片資料庫", images=(CARD,)),)
    result = asyncio.run(built.converse(request("請解析這張名片並存進名片資料庫"), history))
    assert result.status == "answered", result.failure
    assert result.text == "名片內容：王小明。我沒有儲存它。"
    assert len(model.calls) == 2
    retry = model.calls[1]
    assert retry.requirements.vision is True
    roles = [message.role for message in retry.messages]
    assert roles == ["system", "user", "assistant", "user"]
    # The picture is sent once, on the person's own message, never on the retry pair.
    assert [message.images for message in retry.messages] == [(), (CARD,), (), ()]
    assert retry.messages[1].text == "請解析這張名片並存進名片資料庫"
    assert retry.messages[2].text == "名片已經儲存到資料庫了。"
    assert retry.messages[3].text.startswith("[Host check failed]")


def test_a_failed_retry_returns_the_first_answer_with_the_host_note() -> None:
    """The person sees what the first answer found, marked by the Host, never a
    bare "could not complete this turn"."""
    built, model = _host_gateway(
        [], [_text("名片內容：王小明。已經儲存到資料庫了。"), _cut(), _cut(), _cut()]
    )
    history = (ModelMessage(role="user", text="存名片", images=(CARD,)),)
    result = asyncio.run(built.converse(request("存名片"), history))
    assert len(model.calls) == 4
    assert result.status == "answered" and result.failure is None
    assert result.text.startswith("名片內容：王小明。已經儲存到資料庫了。")
    assert CLAIM_NOTE in result.text and "no tool call succeeded" not in result.text
