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

from channels.telegram import MAX_QUOTE_CHARS, _parse
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent

BOT_ANSWER = "sde-weekly-report (1/9)\nDry run: show the plan only"


class Recording:
    """A model that answers plainly and keeps every request it was sent."""

    def __init__(self, text: str = "好的") -> None:
        self.text = text
        self.requests: list[ModelRequest] = []

    def generate(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        return ModelResponse(trace=request.trace, model_alias=request.model_alias, text=self.text)

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
