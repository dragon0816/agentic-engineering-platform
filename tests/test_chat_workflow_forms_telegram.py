"""Telegram: "run X" starts the Workflow's question flow, a model's form
hand-off does too, and a turn never ends without an answer (owner 2026-10-15);
see docs/phases/CHAT_WORKFLOW_FORMS.md."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from test_chat_workflow_forms import RELEASE_SETTINGS
from test_telegram_ingress import (
    OWNER,
    STATUS_MARK,
    FakeReply,
    FakeTransport,
    ingress,
    poll,
    update,
)
from test_telegram_workflow_flow import _install, _tap

from capabilities.release_package.manifest import release_workflow
from common.workflow_run_form import FORM_TOOL
from models.contracts import ModelRequest, ModelResponse, ModelStreamEvent, ModelToolCall

# -- Telegram -----------------------------------------------------------------


def test_telegram_run_x_starts_the_question_flow(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "我要執行rs-wmt-package-release workflow")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.engine.workflows.register(release_workflow())
    agent.gateway.engine.settings_provider = lambda _manifest: RELEASE_SETTINGS
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered"
    assert "rs-wmt-package-release (1/" in (delivery.reply or "")
    assert "Which company is this release for?" in (delivery.reply or "")
    assert item._flows  # waiting for the answer


def test_telegram_names_missing_settings_instead_of_asking_them(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            [update(1, OWNER, "我要執行rs-wmt-package-release workflow")],
            [update(2, OWNER, "/run rs-wmt-package-release")],
        ]
    )
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.engine.workflows.register(release_workflow())
    for _ in range(2):
        delivery = poll(item).deliveries[0]
        assert "these settings are not set" in (delivery.reply or "")
        assert "Agent Web" in (delivery.reply or "") and not item._flows


def test_telegram_prefill_is_answered_and_confirmed(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "run release-validation-form package=quick")]])
    item, agent, _ = ingress(tmp_path, transport)
    _install(agent, [{"name": "package", "label": "Mode", "kind": "text", "required": True}])
    delivery = poll(item).deliveries[0]
    # Nothing left to ask: straight to the confirmation, which shows the value.
    assert delivery.buttons == ((("Run", "run:yes"), ("Cancel", "run:no")),)
    assert "- Mode: quick" in (delivery.reply or "")
    transport.batches.append([_tap(2, OWNER, "run:yes")])
    ran = poll(item).deliveries[0]
    assert ran.outcome is not None and ran.outcome.workflow is not None


def test_telegram_run_of_a_workflow_without_parameters(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "請執行 release-validation-form")]])
    item, agent, _ = ingress(tmp_path, transport)
    _install(agent, [])
    delivery = poll(item).deliveries[0]
    if delivery.disposition == "answered":
        assert delivery.buttons == ((("Run", "run:yes"), ("Cancel", "run:no")),)
    else:
        assert delivery.outcome is not None and delivery.outcome.workflow is not None


class _Scripted:
    """A conversation model: one reply after another."""

    def __init__(self, *replies: dict[str, Any]) -> None:
        self.replies = list(replies)

    def generate(self, item: ModelRequest) -> ModelResponse:
        reply = self.replies.pop(0)
        calls = tuple(
            ModelToolCall(call_id=f"c{index}", name=name, arguments=arguments)
            for index, (name, arguments) in enumerate(reply.get("tools", []))
        )
        return ModelResponse(
            trace=item.trace,
            model_alias=item.model_alias,
            text=reply.get("text", ""),
            tool_calls=calls,
        )

    def stream(self, item: ModelRequest) -> Iterator[ModelStreamEvent]:
        raise NotImplementedError


def test_telegram_follows_the_models_form_hand_off_into_the_flow(tmp_path: Path) -> None:
    from host_runtime.workflow_form_tool import workflow_form_tools

    transport = FakeTransport([[update(1, OWNER, "please do the validation release")]])
    item, agent, _ = ingress(tmp_path, transport)
    _install(
        agent,
        [
            {"name": "package", "label": "Mode", "kind": "text", "required": True},
            {"name": "note", "label": "Note", "kind": "text"},
        ],
    )
    agent.gateway.host_tools = lambda: workflow_form_tools(agent.gateway.engine)
    agent.gateway.router.model = _Scripted(
        {
            "tools": [
                (FORM_TOOL, {"workflow": "release-validation-form", "values": {"package": "quick"}})
            ]
        }
    )
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "answered"
    assert "Note" in (delivery.reply or "") and item._flows  # Mode came with the request
    assert transport.statuses()[-1].startswith("✅ Done")


def test_telegram_never_ends_a_turn_without_an_answer(tmp_path: Path) -> None:
    transport = FakeTransport([[update(1, OWNER, "what can you do")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.router.model = _Scripted({"tools": [("shipment__run", {})]}, {"text": "   "})
    delivery = poll(item).deliveries[0]
    assert delivery.replied and delivery.reply is not None
    assert "gave no answer" in delivery.reply and "/shipment run" in delivery.reply
    assert transport.sent()[-1] == delivery.reply


def test_telegram_says_so_when_an_answer_cannot_be_delivered(tmp_path: Path) -> None:
    class Refusing(FakeTransport):
        def send(self, url: str, body: bytes, headers: Any, timeout_s: float) -> FakeReply:
            payload = json.loads(body)
            if url.endswith("/sendMessage") and payload.get("text") == "Hello":
                self.calls.append((url, payload))
                return FakeReply(400, {"ok": False, "description": "Bad Request"})
            return super().send(url, body, headers, timeout_s)

    transport = Refusing([[update(1, OWNER, "hi")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.router.model = _Scripted({"text": "Hello"})
    delivery = poll(item).deliveries[0]
    assert delivery.replied is False
    sent = [
        payload["text"]
        for url, payload in transport.calls
        if url.endswith("/sendMessage") and not payload["text"].startswith(STATUS_MARK)
    ]
    assert sent[-1].startswith("The answer could not be delivered")


def test_a_rate_limited_answer_is_sent_again(tmp_path: Path) -> None:
    class Limited(FakeTransport):
        limited = False

        def send(self, url: str, body: bytes, headers: Any, timeout_s: float) -> FakeReply:
            payload = json.loads(body)
            if url.endswith("/sendMessage") and payload.get("text") == "Hello" and not self.limited:
                self.limited = True
                self.calls.append((url, payload))
                return FakeReply(429, {"ok": False, "parameters": {"retry_after": 0}})
            return super().send(url, body, headers, timeout_s)

    transport = Limited([[update(1, OWNER, "hi")]])
    item, agent, _ = ingress(tmp_path, transport)
    agent.gateway.router.model = _Scripted({"text": "Hello"})
    delivery = poll(item).deliveries[0]
    assert delivery.replied and transport.sent()[-1] == "Hello"
