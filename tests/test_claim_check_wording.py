"""The completed-action claim check reads conditions and offers as such
(owner report 2026-10-25).

Asked 「再跑一次」, the Agent answered 「如果是已安裝 Workflow，我會開它的執行
表單讓你確認參數」 and got an English Host note saying it had claimed a
completed action. 「已安裝」 there is an adjective inside a condition. The
check now skips a match after a condition, offer or promise in its sentence,
still catches real completed claims, and shows the person a short Traditional
Chinese note while the English reason stays in the log and the retry.
"""

from __future__ import annotations

import asyncio
import logging

import pytest
from test_gateway import _host_gateway, _text, request

from agent.conversation_harness import (
    CLAIM_NOTE,
    CLAIM_REASON,
    MISSING_REASON,
    NOTE_MARK,
    PERSISTENT_NOTE,
    PERSISTENT_REASON,
    check_answer,
    claims_done,
    person_notes,
)

#: Conditional, future and offer phrasing: never a claim of something done.
NOT_CLAIMS = (
    "如果是已安裝 Workflow，我會開它的執行表單讓你確認參數",
    "我不確定你要重跑哪一個；如果是已安裝 Workflow，我會開它的執行表單讓你確認參數。",
    "我可以幫你執行 43W 的週報。",
    "要的話我會幫你產生報告。",
    "若已安裝完成，就可以開始跑。",
    "目前已安裝的 Workflow 有三個。",
    "已完成的步驟會顯示在下面。",
    "I can run the weekly report for you.",
    "If you confirm, I will run it.",
    "Shall I run it now?",
    "Once I have run it, the workbook will be updated.",
)
#: Real completed claims: still caught.
CLAIMS = (
    "已完成。",
    "週報已完成，請查看。",
    "已經幫你寄出草稿。",
    "我已執行 sde-weekly-report。",
    "我已經產生報表。",
    "名片已經儲存到資料庫了。",
    "I have done the weekly report.",
    "I've run it and saved the file.",
    "We have completed the update.",
    # A condition in another sentence does not excuse this one.
    "如果你還需要，可以再說。我已經寫入工作簿了。",
)


@pytest.mark.parametrize("text", NOT_CLAIMS)
def test_conditional_future_and_offer_phrasing_is_not_a_claim(text: str) -> None:
    assert claims_done(text) is False
    checks, reasons = check_answer(text, (), ())
    assert checks[0].status == "passed" and reasons == []


@pytest.mark.parametrize("text", CLAIMS)
def test_real_completed_claims_are_still_caught(text: str) -> None:
    assert claims_done(text) is True
    checks, reasons = check_answer(text, (), ())
    assert checks[0].status == "failed" and reasons == [CLAIM_REASON]


def test_the_person_reads_a_short_chinese_note_and_the_english_stays_in_the_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    built, model = _host_gateway([], [_text("週報已完成。"), _text("我已經跑完了。")])
    with caplog.at_level(logging.WARNING, logger="agent.conversation_harness"):
        result = asyncio.run(built.converse(request("再跑一次"), ()))

    assert len(model.calls) == 2  # one retry, then the note
    assert result.text == "我已經跑完了。\n\n" + CLAIM_NOTE
    assert CLAIM_NOTE == "（系統檢查：這一輪沒有成功執行任何工具，回答中『已完成』的說法未經驗證）"
    assert "no tool call succeeded" not in result.text and "Host 檢查" not in result.text
    assert "Host check failed" in caplog.text and "no tool call succeeded" in caplog.text


def test_the_owners_answer_passes_without_a_retry() -> None:
    answer = "我不確定要重跑哪一個；如果是已安裝 Workflow，我會開它的執行表單讓你確認參數。"
    built, model = _host_gateway([], [_text(answer)])

    result = asyncio.run(built.converse(request("再跑一次"), ()))

    assert len(model.calls) == 1
    assert result.text == answer and NOTE_MARK not in result.text


def test_every_check_has_its_own_note() -> None:
    missing = MISSING_REASON + "C:/t/a.xlsx does not exist; C:/t/b.csv is empty"
    notes = person_notes([CLAIM_REASON, PERSISTENT_REASON, missing, CLAIM_REASON])
    assert notes == [
        CLAIM_NOTE,
        PERSISTENT_NOTE,
        "（系統檢查：回答提到的檔案不存在或是空的：C:/t/a.xlsx（不存在）、C:/t/b.csv（是空的））",
    ]
    assert all(note.startswith(NOTE_MARK) for note in notes)
