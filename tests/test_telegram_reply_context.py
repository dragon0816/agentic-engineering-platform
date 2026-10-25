"""Telegram turns keep their context (owner report 2026-10-25).

The owner used Telegram's Reply on an earlier message and typed 「再跑一次」;
the Agent answered that it did not know what to run again. A Reply now
carries what it replied to, and a turn that did not complete still leaves the
request in the chat's history. Over the fake Bot API of `test_telegram_ingress`;
no socket is opened.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from test_telegram_ingress import OWNER, TOKEN, FakeTransport, ingress, poll, update
from test_telegram_workflow_flow import _install, _tap

from channels.telegram import MAX_QUOTE_CHARS, _parse
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

BOT_ANSWER = "sde-weekly-report (1/9)\nDry run: show the plan only"


class Recording:
    """A model that answers plainly and keeps every request it was sent; the
    first `failures` calls raise instead (a model that is not reachable)."""

    def __init__(self, text: str = "好的", failures: int = 0) -> None:
        self.text = text
        self.failures = failures
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        if self.failures > 0:
            self.failures -= 1
            raise ConnectionError("the gateway is not running")
        return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=self.text)

    def said(self) -> str:
        """Everything the newest request carried."""
        return "\n".join(m.text for m in self.requests[-1].messages)

    def stream(self, request: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError

    def last_person(self) -> str:
        """The newest user message of the newest request."""
        return [m.text for m in self.requests[-1].messages if m.role == "user"][-1]


def replying(
    update_id: int, text: str, replied: dict[str, Any], sender: int = OWNER
) -> dict[str, Any]:
    raw = update(update_id, sender, text)
    raw["message"]["reply_to_message"] = {
        "message_id": 1,
        "chat": {"id": sender, "type": "private"},
        **replied,
    }
    return raw


def test_the_parser_keeps_what_a_message_replies_to() -> None:
    bot = {"from": {"id": 42, "is_bot": True, "first_name": "AEP"}}
    parsed = _parse(replying(5, "再跑一次", {**bot, "text": BOT_ANSWER}))
    assert parsed is not None and parsed.quoted == BOT_ANSWER
    caption = _parse(replying(6, "這張", {"photo": [{"file_id": "p"}], "caption": "週報圖"}))
    assert caption is not None and caption.quoted == "週報圖"
    bare = _parse(replying(7, "這個", {"sticker": {"file_id": "s"}}))
    assert bare is not None and bare.quoted == "（附件）"
    plain = _parse(update(8, OWNER, "hello"))
    assert plain is not None and plain.quoted is None
    long = _parse(replying(9, "這段", {"text": "長" * 3000}))
    assert long is not None and long.quoted == "長" * MAX_QUOTE_CHARS + "…"
    secret = _parse(replying(10, "這段", {"text": f"bot{TOKEN} Authorization: Bearer abc"}))
    assert secret is not None and secret.quoted is not None
    assert TOKEN not in secret.quoted and "Bearer abc" not in secret.quoted


def test_a_reply_to_the_bots_answer_reaches_the_model_with_the_quote(tmp_path: Path) -> None:
    transport = FakeTransport(
        [[replying(1, "再跑一次", {"from": {"id": 42, "is_bot": True}, "text": BOT_ANSWER})]]
    )
    item, agent, _ = ingress(tmp_path, transport)
    model = Recording()
    agent.gateway.router.model = model

    delivery = poll(item).deliveries[0]

    assert delivery.disposition == "answered"
    person = model.last_person()
    assert person.startswith("（回覆先前的訊息：「sde-weekly-report (1/9)")
    assert person.endswith("」）\n再跑一次")
    # The history keeps it, so the next turn still knows what was meant.
    (history,) = item._histories.values()
    assert history[0].text == person


def test_a_reply_to_the_persons_own_message_is_quoted_too(tmp_path: Path) -> None:
    own = {"from": {"id": OWNER, "is_bot": False}, "text": "幫我執行 43W SDE weekly report"}
    transport = FakeTransport([[replying(1, "再跑一次", own)]])
    item, agent, _ = ingress(tmp_path, transport)
    model = Recording()
    agent.gateway.router.model = model

    poll(item)

    assert model.last_person() == "（回覆先前的訊息：「幫我執行 43W SDE weekly report」）\n再跑一次"


def test_a_failed_turn_stays_in_history_so_run_again_has_the_request(tmp_path: Path) -> None:
    transport = FakeTransport(
        [[update(1, OWNER, "幫我整理這週的 GitHub 進度")], [update(2, OWNER, "再跑一次")]]
    )
    item, agent, _ = ingress(tmp_path, transport)
    model = Recording(failures=1)
    agent.gateway.router.model = model

    failed = poll(item).deliveries[0]
    assert failed.disposition == "answered" and "could not be answered" in (failed.reply or "")
    (history,) = item._histories.values()
    assert [message.role for message in history] == ["user", "assistant"]
    assert history[0].text == "幫我整理這週的 GitHub 進度"
    assert history[1].text.startswith("（上一輪沒有完成：")

    poll(item)

    said = model.said()
    assert "幫我整理這週的 GitHub 進度" in said and "（上一輪沒有完成：" in said
    assert model.last_person() == "再跑一次"


def test_a_workflow_question_flow_stays_in_history_too(tmp_path: Path) -> None:
    """The 09:34 request was a Workflow run request: it opened the Workflow's
    questions and never reached the model, so nothing of it was kept."""
    transport = FakeTransport([[update(1, OWNER, "幫我執行 release-validation-form")]])
    item, agent, _ = ingress(tmp_path, transport)
    _install(agent, [{"name": "package", "label": "Mode", "kind": "text", "required": True}])
    model = Recording()
    agent.gateway.router.model = model

    opened = poll(item).deliveries[0]

    assert "Mode *" in (opened.reply or "") and model.requests == []
    (history,) = item._histories.values()
    assert history[0].text == "幫我執行 release-validation-form"
    assert history[1].text.startswith("（交給 Workflow engineering/release-validation-form")
    assert "Mode *" in history[1].text
    # The questions expire unanswered; 「再跑一次」 then reaches the model with them.
    for state in item._flows.values():
        state.started -= 3600
    transport.batches.append([update(2, OWNER, "再跑一次")])
    poll(item)
    assert "幫我執行 release-validation-form" in model.said()
    # A finished run is kept as well.
    transport.batches += [[update(3, OWNER, "/run 7")], [update(4, OWNER, "quick")]]
    poll(item)
    final = poll(item).deliveries[0]
    assert final.disposition == "answered"  # the card waits for the tap
    transport.batches.append([_tap(5, OWNER, "run:yes", transport)])
    final = poll(item).deliveries[0]
    assert final.disposition == "routed"
    (history,) = item._histories.values()
    assert history[-2].text == "【執行】release-validation-form"
    assert history[-1].text.startswith("release-validation-form run ")
