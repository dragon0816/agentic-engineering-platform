"""Telegram question flow from the Workflow declaration (slice S4, pure part)."""

from __future__ import annotations

from typing import Any

from test_workflow_parameter_declaration import _manifest

from channels import telegram_flow as flow

FIELDS: list[dict[str, Any]] = [
    {
        "name": "project",
        "label": "Project",
        "kind": "text",
        "required": True,
        "group": "identity",
        "order": 10,
        "pattern": "^[a-z]+$",
    },
    {
        "name": "mode",
        "label": "Mode",
        "kind": "select",
        "order": 20,
        "default": "brief",
        "choices": [{"value": "brief", "label": "Brief"}, {"value": "full", "label": "Full"}],
    },
    {"name": "cc", "label": "CC", "kind": "emails", "order": 30},
    {"name": "limit", "label": "Limit", "kind": "integer", "order": 40, "minimum": 1},
    {"name": "send", "label": "Send mail", "kind": "boolean", "order": 50, "confirm": True},
    {"name": "folder", "label": "Folder", "kind": "folder", "channels": ["web"]},
]


def _state(effect: str = "read", fields: list[dict[str, Any]] | None = None) -> flow.FlowState:
    started = flow.start(_manifest(fields or FIELDS), effect)
    assert isinstance(started, flow.FlowState)
    return started


def test_questions_follow_the_telegram_channel_in_form_order() -> None:
    state = _state()
    assert [item.name for item in state.fields] == ["project", "mode", "cc", "limit", "send"]
    first = flow.begin(state)
    assert first.kind == "ask" and first.prompt is not None
    assert "Project *" in first.prompt.text and "Required." in first.prompt.text


def test_buttons_answers_skip_and_validation() -> None:
    state = _state()
    flow.begin(state)
    assert flow.answer(state, "/skip").prompt.text.startswith("This field is required")
    assert "does not match" in flow.answer(state, "Bad Name").prompt.text
    mode = flow.answer(state, "rsx")
    assert mode.prompt is not None
    assert mode.prompt.buttons == [[("Brief", "brief"), ("Full", "full")]]
    flow.answer(state, "Full")  # matched by label
    flow.answer(state, "a@example.com, b@example.com")  # list kind
    assert "whole number" in flow.answer(state, "many").prompt.text
    assert "minimum" in flow.answer(state, "0").prompt.text
    flow.answer(state, "5")
    send = flow.prompt(state)
    assert send.buttons == [[("Yes", "yes"), ("No", "no")]]
    done = flow.answer(state, "no")
    assert done.kind == "ready"
    assert done.arguments == {
        "project": "rsx",
        "mode": "full",
        "cc": ["a@example.com", "b@example.com"],
        "limit": 5,
        "send": False,
    }


def test_effectful_or_privileged_runs_need_a_confirmation_tap() -> None:
    state = _state(effect="write")
    flow.begin(state)
    for reply in ("rsx", "/skip", "/skip", "/skip", "/skip"):
        step = flow.answer(state, reply)
    assert step.kind == "ask" and step.prompt is not None
    assert step.prompt.buttons == [[("Run", "run:yes"), ("Cancel", "run:no")]]
    assert "effects: write" in step.prompt.text
    ready = flow.answer(state, "run:yes")
    assert ready.kind == "ready" and ready.arguments == {"project": "rsx", "mode": "brief"}

    privileged = _state(effect="read")
    flow.begin(privileged)
    for reply in ("rsx", "/skip", "/skip", "/skip"):
        flow.answer(privileged, reply)
    confirm = flow.answer(privileged, "yes")  # send = true is privileged
    assert confirm.kind == "ask" and "(privileged)" in confirm.prompt.text
    assert flow.answer(privileged, "run:no").kind == "cancelled"


def test_cancel_and_required_upload_refusal() -> None:
    state = _state()
    flow.begin(state)
    assert flow.answer(state, "/cancel").kind == "cancelled"
    refused = flow.start(
        _manifest(
            [
                {"name": "file", "label": "Requirements", "kind": "upload", "required": True},
            ]
        ),
        "read",
    )
    assert isinstance(refused, str) and "Agent Web" in refused
    optional = flow.start(
        _manifest(
            [
                {"name": "file", "label": "Requirements", "kind": "upload"},
            ]
        ),
        "read",
    )
    assert isinstance(optional, flow.FlowState) and optional.fields == ()
    assert flow.begin(optional).kind == "ready"
