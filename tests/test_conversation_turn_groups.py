"""Grouped conversation turns: replying to an exchange and rating an answer."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from test_agent_web import base, fetch
from test_host_models import GatewayReply, binding, endpoint
from test_host_wiring import ready

from host_runtime.conversation_context import ConversationContextSettings
from host_runtime.conversations import (
    ConversationFeedbackRequest,
    ConversationMessage,
    ConversationTurnRequest,
)
from host_runtime.host import build_runtime
from host_runtime.web import AgentWeb, AgentWebServer
from host_runtime.web_page import PAGE


class _ChatGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send(
        self, url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
    ) -> GatewayReply:
        self.calls.append(json.loads(body))
        return GatewayReply(
            200, {"choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}}]},
        )


def _chat_config(tmp_path: Path) -> tuple[Any, Any]:
    return ready(
        tmp_path,
        config_changes={
            "models": binding(
                catalog={
                    "endpoints": [endpoint(credential=None, model="fixture-model")],
                    "routes": [{"name": "default", "alias": "company"}],
                }
            )
        },
    )


def test_a_message_cannot_carry_the_other_roles_annotations() -> None:
    from datetime import UTC, datetime

    from host_runtime.conversations import MessageFeedback

    now = datetime.now(UTC)
    with pytest.raises(ValueError, match="rates an answer"):
        ConversationMessage(
            message_id="m1", role="user", text="q", created_at=now, status="submitted",
            feedback=MessageFeedback(rating="up", updated_at=now),
        )
    with pytest.raises(ValueError, match="only a question replies"):
        ConversationMessage(
            message_id="m2", role="assistant", text="a", created_at=now, status="answered",
            reply_to="m0",
        )


def test_reply_keeps_the_chosen_exchange_directly_before_the_new_question(
    tmp_path: Path,
) -> None:
    config, layout = _chat_config(tmp_path)
    transport = _ChatGateway()
    with build_runtime(config, layout=layout, model_transport=transport) as runtime:
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        web.update_context_settings(
            ConversationContextSettings(recent_messages=3, history_budget_bytes=4_000)
        )
        for number in range(4):
            web.conversation_turn(
                ConversationTurnRequest(session_id=session, message=f"question {number}")
            )
        record = web.conversations(session)["selected"]
        first_answer = record["messages"][1]["message_id"]
        reply = web.conversation_turn(ConversationTurnRequest(
            session_id=session, message="follow up", reply_to=first_answer,
        ))
        assert reply["ok"] is True
        # The window of three keeps the replied exchange even though it is old.
        assert [item["content"] for item in transport.calls[-1]["messages"][1:]] == [
            "question 0", "ok", "follow up",
        ]
        stored = web.conversations(session)["selected"]["messages"]
        assert stored[-2]["reply_to"] == first_answer
        calls = len(transport.calls)
        unknown = web.conversation_turn(ConversationTurnRequest(
            session_id=session, message="again", reply_to="message-unknown",
        ))
        assert unknown["answer"]["status"] == "needs_input"
        assert len(transport.calls) == calls


def test_feedback_annotates_one_answer_without_rewriting_the_transcript(
    tmp_path: Path,
) -> None:
    config, layout = _chat_config(tmp_path)
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        web = AgentWeb(runtime)
        session = web.create_conversation()["conversation"]["session_id"]
        web.conversation_turn(ConversationTurnRequest(session_id=session, message="hello"))
        before = web.conversations(session)["selected"]
        answer_id = before["messages"][1]["message_id"]
        saved = web.conversation_feedback(ConversationFeedbackRequest(
            session_id=session, message_id=answer_id, rating="down", note="  缺 option 證據 ",
        ))
        assert saved["ok"] is True
        assert saved["feedback"]["rating"] == "down"
        assert saved["feedback"]["note"] == "缺 option 證據"
        after = web.conversations(session)["selected"]
        assert after["updated_at"] == before["updated_at"]
        assert after["messages"][1]["text"] == before["messages"][1]["text"]
        assert after["messages"][1]["feedback"]["rating"] == "down"
        changed = web.conversation_feedback(ConversationFeedbackRequest(
            session_id=session, message_id=answer_id, rating="neutral",
        ))
        assert changed["feedback"] == {**changed["feedback"], "rating": "neutral", "note": None}
        question_id = after["messages"][0]["message_id"]
        refused = web.conversation_feedback(ConversationFeedbackRequest(
            session_id=session, message_id=question_id, rating="up",
        ))
        assert refused == {"ok": False, "code": "conversation_message_unknown"}
        # The transcript still accepts new turns after an annotation.
        assert web.conversation_turn(
            ConversationTurnRequest(session_id=session, message="next")
        )["ok"] is True
        assert len(web.conversations(session)["selected"]["messages"]) == 4


def test_feedback_endpoint_is_authenticated_and_validated(tmp_path: Path) -> None:
    config, layout = _chat_config(tmp_path)
    with build_runtime(config, layout=layout, model_transport=_ChatGateway()) as runtime:
        server = AgentWebServer(AgentWeb(runtime))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            endpoint_url = base(server) + "/api/conversations/feedback"
            created = fetch(
                base(server) + "/api/conversations", token=server.token, body={}
            ).json()["conversation"]
            fetch(
                base(server) + "/api/conversations/turn", token=server.token,
                body={"session_id": created["session_id"], "message": "hello"},
            )
            selected = fetch(
                base(server) + "/api/conversations?session_id=" + created["session_id"],
                token=server.token,
            ).json()["selected"]
            body = {
                "session_id": created["session_id"],
                "message_id": selected["messages"][1]["message_id"], "rating": "up",
            }
            assert fetch(endpoint_url, body=body).status == 401
            assert fetch(endpoint_url, token=server.token,
                         body={**body, "rating": "great"}).status == 400
            accepted = fetch(endpoint_url, token=server.token, body=body)
            assert accepted.status == 200 and accepted.json()["feedback"]["rating"] == "up"
            assert fetch(endpoint_url, token=server.token,
                         body={**body, "message_id": "message-x"}).status == 404
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


# -- Page ---------------------------------------------------------------------

START = "// -- Turn groups ---"
END = "// -- end Turn groups"


def _script() -> str:
    return PAGE.split("<script>", 1)[1].split("</script>", 1)[0]


def test_the_page_groups_turns_with_rating_reply_and_context_menu() -> None:
    for expected in (
        'id="turn-menu"', 'id="reply-chip"', 'id="reply-chip-clear"',
        '"/api/conversations/feedback"', '"contextmenu"', "reply_to: replying.message_id",
        'role", "group"', "aria-pressed",
    ):
        assert expected in PAGE, expected
    section = _script().split(START, 1)[1].split(END, 1)[0]
    for unsafe in ("innerHTML", "insertAdjacentHTML", "outerHTML"):
        assert unsafe not in section


def test_turn_renderers_keep_hostile_text_as_text(tmp_path: Path) -> None:
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is not installed, so the renderers cannot be exercised")
    source = START + _script().split(START, 1)[1].split(END, 1)[0]
    harness = r"""
const assert = require("node:assert/strict");
class FakeNode {
  constructor(tag, value = "") {
    this.tag = tag; this.value = value; this.children = []; this.attrs = {};
    this.listeners = {}; this.dataset = {}; this.className = "";
  }
  append(...children) { this.children.push(...children); }
  replaceChildren(...children) { this.children = children; }
  setAttribute(name, value) { this.attrs[name] = value; }
  addEventListener(name, handler) { this.listeners[name] = handler; }
}
const document = {
  createElement: tag => new FakeNode(tag),
  createTextNode: value => new FakeNode("#text", value),
};
const text = value => document.createTextNode(value == null ? "" : String(value));
const api = new Function("document", "text", __SOURCE__ +
  "\nreturn {turnBlock, feedbackSummary, attachTurnControls};")(document, text);
const all = node => [node, ...node.children.flatMap(all)];
const content = node => node.tag === "#text" ? node.value : node.children.map(content).join("");
const HOSTILE = __HOSTILE__;
const block = api.turnBlock(HOSTILE, HOSTILE);
api.attachTurnControls(block, HOSTILE, {message_id: "m1", text: HOSTILE,
  feedback: {rating: "down", note: HOSTILE}});
for (const item of all(block)) {
  assert.ok(item.tag === "#text" || !("innerHTML" in item));
  if (item.tag !== "#text") assert.ok(!["img", "script"].includes(item.tag));
}
assert.ok(content(block).includes(HOSTILE));
assert.equal(block.attrs.role, "group");
assert.ok(block.listeners.contextmenu);
const pressed = all(block).filter(item => item.attrs["aria-pressed"] === "true");
assert.equal(pressed.length, 1);
assert.equal(pressed[0].dataset.rating, "down");
assert.ok(content(api.feedbackSummary({rating: "up", note: HOSTILE})).includes(HOSTILE));
"""
    script = tmp_path / "turns.js"
    script.write_text(
        harness.replace("__SOURCE__", json.dumps(source))
        .replace("__HOSTILE__", json.dumps("<img src=x onerror=alert(1)>")),
        encoding="utf-8",
    )
    completed = subprocess.run(
        [node, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60
    )
    assert completed.returncode == 0, completed.stderr
