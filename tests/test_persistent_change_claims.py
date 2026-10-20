"""The Host catches "I changed the rule" with nothing saved (owner 2026-10-20).

Live test 2026-10-20: the person said 「執行時不需要問是否包含在職人員…」 and the
Agent answered 「規則我已改成…」 after only a read tool (`cards__list`); nothing
persistent changed. `no_unbacked_action_claim` now also needs a tool that
changes something, not only reads, to back a claim of a lasting change.
"""

from __future__ import annotations

import asyncio
from typing import Any

from test_gateway import _call, _host_gateway, _text, request

from agent.conversation_harness import check_answer
from agent.gateway import ConversationToolExecution, HostTool, HostToolOutcome
from common.execution import Failure, RequestContext
from models.contracts import ModelTool


def _done(name: str, status: str = "succeeded") -> ConversationToolExecution:
    return ConversationToolExecution(
        call_id="c1",
        name=name,
        host=HostToolOutcome(
            status=status,
            failure=Failure(code="x", message="m") if status == "failed" else None,
        ),
    )


def _claim_failed(text: str, *tools: ConversationToolExecution) -> bool:
    checks, _reasons = check_answer(text, tools, ())
    return checks[0].status == "failed"


CLAIMS = (
    "好的，規則我已改成：以後執行時不再詢問是否包含在職人員。",
    "已改成只列在職人員。",
    "已設定為預設排除離職人員。",
    "收到，已更新規則。",
    "我已記住這個偏好。",
    "以後都會直接產生，不再詢問。",
    "I've updated the rule so it no longer asks.",
    "Got it. From now on I will skip that question.",
    "I'll remember that you want only current staff.",
)


def test_a_lasting_change_claim_with_no_tool_or_only_a_read_is_flagged() -> None:
    for text in CLAIMS:
        assert _claim_failed(text), text
        # The live case: a read tool succeeded, nothing was changed.
        assert _claim_failed(text, _done("cards__list")), text
        assert _claim_failed(text, _done("authoring__get_workflow")), text
        # A changing tool that failed backs nothing.
        assert _claim_failed(text, _done("cards__edit_person", "failed")), text
    _checks, reasons = check_answer(CLAIMS[0], (_done("cards__list"),), ())
    assert "lasting change" in reasons[0] and "Workflow" in reasons[0]


def test_a_lasting_change_backed_by_a_tool_that_changed_something_is_not_flagged() -> None:
    for name in ("cards__edit_person", "authoring__draft_workflow", "propose_change"):
        for text in CLAIMS:
            assert not _claim_failed(text, _done("cards__list"), _done(name)), (name, text)


def test_neutral_text_is_not_flagged() -> None:
    for text in (
        "請問執行時要不要包含已離職的人員？",
        "你的資料夾已設定為 C:\\data，這次就用它。",
        "如果以後都會用到，我可以幫你起草一個 Workflow，按下安裝後才會保存。",
        "這個規則目前只套用在這次對話，還沒有保存。",
        "安裝以後會出現在 Capabilities。",
        "The rule applies to this conversation only; it is not saved.",
        "If you want this every time, I can draft a Workflow for you to install.",
    ):
        assert not _claim_failed(text), text
        assert not _claim_failed(text, _done("cards__list")), text


def test_the_claim_after_a_read_gets_one_retry_and_the_prompt_says_there_is_no_memory() -> None:
    async def listed(context: RequestContext, args: dict[str, Any]) -> HostToolOutcome:
        return HostToolOutcome(status="succeeded", data={"people": 3})

    read = HostTool(
        ModelTool(
            name="cards__list",
            description="List people.",
            input_contract="x.v1",
            input_schema={"type": "object"},
        ),
        listed,
    )
    built, model = _host_gateway(
        [read],
        [
            _call("cards__list", {}),
            _text("規則我已改成：執行時不再詢問是否包含在職人員。"),
            _text("這次對話裡我不會再問；這個規則還沒有保存，要我起草一個 Workflow 讓你安裝嗎？"),
        ],
    )
    result = asyncio.run(built.converse(request("執行時不需要問是否包含在職人員"), ()))
    assert result.text.startswith("這次對話裡我不會再問")
    assert "Host 檢查未通過" not in result.text
    assert len(model.calls) == 3
    feedback = model.calls[2].messages[-1].text
    assert feedback.startswith("[Host check failed]") and "lasting change" in feedback
    system = model.calls[0].messages[0].text
    assert "You keep no rule" in system and "propose_change" in system
