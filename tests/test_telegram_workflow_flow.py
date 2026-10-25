"""Telegram `/run` question flow end to end through the ingress (slice S4)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from evaluation_runner import release_workflow
from test_telegram_ingress import OWNER, STRANGER, FakeTransport, ingress, poll, update

from common.assets import WorkflowManifest


def _install(agent: Any, parameters: list[dict[str, Any]], **extra: Any) -> WorkflowManifest:
    data = release_workflow().model_dump(mode="json")
    data["metadata"]["identity"]["name"] = "release-validation-form"
    data["run_alias"] = 7
    data["parameters"] = parameters
    data.update(extra)
    manifest = WorkflowManifest.model_validate(data)
    agent.gateway.engine.workflows.register(manifest)
    return manifest


def _keyboard_message(transport: FakeTransport) -> int:
    """The id the fake Bot API gave the newest message sent with buttons."""
    newest = 1
    sent = [payload for url, payload in transport.calls if url.endswith("/sendMessage")]
    for position, payload in enumerate(sent, start=1):
        if "reply_markup" in payload:
            newest = position
    return newest


def _tap(
    update_id: int, sender: int, data: str, transport: FakeTransport | None = None
) -> dict[str, Any]:
    """A button tap; with `transport`, on the newest message with buttons (a
    question flow takes taps only on the question it waits on)."""
    message_id = _keyboard_message(transport) if transport is not None else 1
    return {
        "update_id": update_id,
        "callback_query": {
            "id": f"cb-{update_id}",
            "from": {"id": sender, "is_bot": False},
            "message": {"message_id": message_id, "chat": {"id": sender, "type": "private"}},
            "data": data,
        },
    }


def test_run_asks_each_field_then_executes_through_the_agent(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            [update(1, OWNER, "/run 7")],
            [update(2, OWNER, "BAD")],
            [update(3, OWNER, "quick")],
        ]
    )
    item, agent, runner = ingress(tmp_path, transport)
    _install(
        agent,
        [
            {
                "name": "package",
                "label": "Mode",
                "kind": "text",
                "required": True,
                "pattern": "^[a-z]+$",
                "help": "lower-case word",
            },
        ],
    )
    first = poll(item).deliveries[0]
    assert first.disposition == "answered" and "Mode *" in (first.reply or "")
    assert "lower-case word" in (first.reply or "")
    again = poll(item).deliveries[0]
    assert "does not match" in (again.reply or "")
    final = poll(item)
    delivery = final.deliveries[0]
    # Every run waits for the card's tap (owner 2026-10-25).
    assert delivery.disposition == "answered" and "- Mode：quick" in (delivery.reply or "")
    assert delivery.buttons == ((("確認執行", "run:yes"), ("修改", "run:edit")),)
    transport.batches.append([_tap(4, OWNER, "run:yes", transport)])
    delivery = poll(item).deliveries[0]
    assert delivery.disposition == "routed" and delivery.outcome is not None
    assert delivery.outcome.ingress == "telegram"
    assert delivery.outcome.workflow is not None
    assert delivery.outcome.workflow.run.status == "succeeded"
    assert "release-validation-form run" in (delivery.reply or "")


def test_choice_fields_send_an_inline_keyboard_and_taps_are_acknowledged(
    tmp_path: Path,
) -> None:
    transport = FakeTransport([[update(1, OWNER, "/run release-validation-form")]])
    item, agent, _runner = ingress(tmp_path, transport)
    _install(
        agent,
        [
            {
                "name": "package",
                "label": "Mode",
                "kind": "select",
                "required": True,
                "choices": [
                    {"value": "quick", "label": "Quick"},
                    {"value": "deep", "label": "Deep"},
                ],
            },
        ],
    )
    first = poll(item).deliveries[0]
    assert first.buttons == ((("Quick", "quick"), ("Deep", "deep")),)
    sent = [payload for url, payload in transport.calls if url.endswith("/sendMessage")]
    assert sent[-1]["reply_markup"] == {
        "inline_keyboard": [
            [
                {"text": "Quick", "callback_data": "quick"},
                {"text": "Deep", "callback_data": "deep"},
            ]
        ]
    }
    transport.batches.append([_tap(2, OWNER, "deep", transport)])
    card = poll(item).deliveries[0]
    assert "- Mode：deep" in (card.reply or "")
    acknowledged = [
        payload for url, payload in transport.calls if url.endswith("/answerCallbackQuery")
    ]
    assert acknowledged == [{"callback_query_id": "cb-2"}]


def test_cancel_unknown_workflow_and_unmapped_sender(tmp_path: Path) -> None:
    transport = FakeTransport(
        [
            [update(1, OWNER, "/run 7")],
            [update(2, OWNER, "/cancel")],
            [update(3, OWNER, "/run nothing-like-it")],
            [update(4, STRANGER, "/run 7")],
        ]
    )
    item, agent, runner = ingress(tmp_path, transport)
    _install(agent, [{"name": "package", "label": "Mode", "kind": "text", "required": True}])
    poll(item)
    assert poll(item).deliveries[0].reply == "Cancelled."
    assert "No single installed Workflow" in (poll(item).deliveries[0].reply or "")
    stranger = poll(item).deliveries[0]
    assert stranger.disposition == "unmapped_sender" and stranger.reply is None
    assert runner.bridge.events == ()


def test_an_effectful_workflow_waits_for_the_run_tap(tmp_path: Path) -> None:
    from evaluation_runner import release_package_workflow

    transport = FakeTransport([[update(1, OWNER, "/run 8")]])
    item, agent, runner = ingress(tmp_path, transport)
    data = release_package_workflow().model_dump(mode="json")
    data["metadata"]["identity"]["name"] = "release-package-form"
    data["run_alias"] = 8
    data["parameters"] = [{"name": "package", "label": "Package", "kind": "text"}]
    agent.gateway.engine.workflows.register(WorkflowManifest.model_validate(data))
    waiting = poll(item).deliveries[0]  # nothing required: straight to the card
    assert waiting.disposition == "answered"
    assert "effects: external_side_effect" in (waiting.reply or "")
    assert waiting.buttons == ((("確認執行", "run:yes"), ("修改", "run:edit")),)
    assert runner.bridge.events == ()  # nothing ran before the tap
    transport.batches.append([_tap(3, OWNER, "run:no", transport)])
    assert poll(item).deliveries[0].reply == "Cancelled."
    assert runner.bridge.events == ()
