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


def _text(step: flow.FlowStep) -> str:
    """The prompt text of a step that asks."""
    assert step.prompt is not None
    return step.prompt.text


def test_questions_follow_the_telegram_channel_in_form_order() -> None:
    state = _state()
    assert [item.name for item in state.fields] == ["project", "mode", "cc", "limit", "send"]
    first = flow.begin(state)
    assert first.kind == "ask" and first.prompt is not None
    assert "Project *" in first.prompt.text and "Required." in first.prompt.text


def test_only_required_fields_are_asked_then_one_card_lists_every_value() -> None:
    """Owner 2026-10-25: optional fields take their defaults and are not
    asked one by one; the card shows where each value came from."""
    state = _state()
    flow.begin(state)
    assert "(1/1)" in flow.prompt(state).text  # only Project is required
    assert _text(flow.answer(state, "/skip")).startswith("This field is required")
    assert "does not match" in _text(flow.answer(state, "Bad Name"))
    card = flow.answer(state, "rsx")
    assert card.kind == "ask" and card.prompt is not None
    assert card.prompt.buttons == [[("確認執行", "run:yes"), ("修改", "run:edit")]]
    assert "- Project：rsx" in card.prompt.text
    assert "- Mode：brief（預設）" in card.prompt.text
    assert "未填（不使用）：CC、Limit、Send mail" in card.prompt.text
    ready = flow.answer(state, "run:yes")
    assert ready.kind == "ready" and ready.arguments == {"project": "rsx", "mode": "brief"}


def test_the_card_changes_values_by_button_or_by_typed_text() -> None:
    state = _state()
    flow.begin(state)
    flow.answer(state, "rsx")
    menu = flow.answer(state, "修改")
    assert menu.prompt is not None and ("Mode", "edit:1") in menu.prompt.buttons[0]
    mode = flow.answer(state, "edit:1")
    assert mode.prompt is not None and "(修改)" in mode.prompt.text
    assert mode.prompt.buttons == [[("Brief", "brief"), ("Full", "full")]]
    back = flow.answer(state, "Full")  # matched by label; the card comes back
    assert back.prompt is not None and "- Mode：full" in back.prompt.text
    assert "已改：CC = a@example.com, b@example.com" in _text(
        flow.answer(state, "CC a@example.com, b@example.com")
    )
    assert "whole number；沒有改" in _text(flow.answer(state, "limit many"))
    assert "minimum" in _text(flow.answer(state, "Limit 0"))
    flow.answer(state, "limit = 5")
    assert "Send mail = 是" in _text(flow.answer(state, "send mail"))  # a switch flips
    assert "- Send mail (privileged)：否" in _text(flow.answer(state, "Send mail 改成否"))
    assert "看不懂要改哪一項" in _text(flow.answer(state, "whatever this is"))
    done = flow.answer(state, "確認執行")
    assert done.kind == "ready"
    assert done.arguments == {
        "project": "rsx",
        "mode": "full",
        "cc": ["a@example.com", "b@example.com"],
        "limit": 5,
        "send": False,
    }


def test_given_values_are_not_asked_and_are_marked_on_the_card() -> None:
    started = flow.start(_manifest(FIELDS), "write", prefill={"project": "abc", "limit": 3})
    assert isinstance(started, flow.FlowState)
    text = _text(flow.begin(started))
    assert text.startswith("執行 inspect？") and "effects: write" in text
    assert "- Project：abc（從你的訊息）" in text and "- Limit：3（從你的訊息）" in text
    assert flow.prefill_note(started) == "已從你的訊息帶入：Project = abc；Limit = 3"
    assert flow.answer(started, "run:no").kind == "cancelled"


def test_a_given_value_is_announced_on_the_first_question() -> None:
    fields = [
        {"name": "week", "label": "Report week", "kind": "text", "required": True},
        {"name": "repo", "label": "Repository", "kind": "text", "required": True},
    ]
    started = flow.start(_manifest(fields), "read", prefill={"week": "2026_43W"})
    assert isinstance(started, flow.FlowState)
    first = _text(flow.begin(started))
    assert first.startswith("已從你的訊息帶入：Report week = 2026_43W\n")
    assert "(1/1)" in first and "Repository *" in first


def test_a_boolean_question_waits_for_yes_or_no() -> None:
    fields = [{"name": "go", "label": "Go ahead", "kind": "boolean", "required": True}]
    state = _state(fields=fields)
    asked = flow.begin(state)
    assert asked.prompt is not None and asked.prompt.buttons == [[("Yes", "yes"), ("No", "no")]]
    assert "answer yes or no" in _text(flow.answer(state, "有輸入過的參數能不能自己填啊？"))
    assert flow.current_field(state) is not None  # still waiting on the same question
    card = flow.answer(state, "yes")
    assert card.prompt is not None and "- Go ahead：是" in card.prompt.text
    assert flow.answer(state, "run:yes").arguments == {"go": True}


def test_a_reply_to_an_earlier_question_sets_that_field() -> None:
    fields = [
        {"name": "week", "label": "Report week", "kind": "text", "required": True},
        {"name": "repo", "label": "Repository", "kind": "text", "required": True},
    ]
    state = _state(fields=fields)
    first = _text(flow.begin(state))
    assert flow.quoted_question(first) == ("inspect", "Report week")
    flow.answer(state, "2026_43W")
    again = flow.answer_field(state, "week", "2026_44W")  # a Reply on question 1
    assert "Repository *" in _text(again)  # still waiting on question 2
    card = flow.answer(state, "owner/repo")
    assert "- Report week：2026_44W" in _text(card)
    assert flow.quoted_question("inspect (修改)\nRepository *\nRequired.") == (
        "inspect",
        "Repository",
    )
    assert flow.quoted_question("執行 inspect？") is None


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
    assert flow.begin(optional).kind == "ready"  # nothing to show, read-only: runs
