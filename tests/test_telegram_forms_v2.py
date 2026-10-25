"""Telegram forms v2 (owner 2026-10-15): multi-select buttons, pick-or-type,
uploads as documents and "same as last time", in the pure flow and through
the ingress over the fake Bot API."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from test_telegram_attachments import FileTransport, message
from test_telegram_ingress import OWNER, ingress, poll, update
from test_telegram_workflow_flow import _install, _tap
from test_workflow_parameter_declaration import _manifest

from channels import telegram_flow as flow
from host_runtime.identity_presets import IdentityPresets
from host_runtime.workflow_uploads import WorkflowUploadStore

# Required: since 2026-10-25 only required fields are asked one by one.
PLANS = {
    "name": "plans",
    "label": "Plans",
    "kind": "select",
    "multiple": True,
    "required": True,
    "choices": [{"value": "a.json"}, {"value": "b.json"}, {"value": "c.json"}],
}


def _state(fields: list[dict[str, Any]], **kwargs: Any) -> flow.FlowState:
    started = flow.start(_manifest(fields), "read", **kwargs)
    assert isinstance(started, flow.FlowState)
    return started


def _confirmed(state: flow.FlowState, step: flow.FlowStep) -> dict[str, Any] | None:
    """The run's arguments once the card that follows the last answer is confirmed."""
    assert step.kind == "ask" and state.confirming, step
    return flow.answer(state, "run:yes").arguments


def test_multi_select_toggles_in_place_then_done() -> None:
    state = _state([PLANS])
    first = flow.begin(state)
    assert first.prompt is not None
    assert first.prompt.buttons == [
        [("a.json", "pick:1"), ("b.json", "pick:2"), ("c.json", "pick:3")],
        [("Done", "pick:done")],
    ]
    toggled = flow.answer(state, "pick:3")
    assert toggled.prompt is not None and toggled.prompt.edit
    assert toggled.prompt.buttons[0][2] == (flow.CHECK + "c.json", "pick:3")
    flow.answer(state, "pick:1")
    flow.answer(state, "pick:3")  # untick
    done = flow.answer(state, "pick:done")
    assert _confirmed(state, done) == {"plans": ["a.json"]}
    # Typing still works.
    typed = _state([PLANS])
    flow.begin(typed)
    step = flow.answer(typed, "b.json, c.json")
    assert _confirmed(typed, step) == {"plans": ["b.json", "c.json"]}


def test_a_required_multi_select_needs_one_tick_and_many_choices_are_capped() -> None:
    state = _state([PLANS])
    flow.begin(state)
    assert (
        "Tick at least one" in (flow.answer(state, "pick:done").prompt or flow.FlowPrompt("")).text
    )
    many = _state([{**PLANS, "choices": [{"value": f"v{index}"} for index in range(120)]}])
    buttons = flow.begin(many).prompt.buttons  # type: ignore[union-attr]
    assert sum(len(row) for row in buttons) == flow.MAX_BUTTONS + 1
    assert all(len(row) <= flow.BUTTONS_PER_ROW for row in buttons)
    assert "v119" in flow.prompt(many).text  # the rest is listed for typing


def test_pick_or_type_takes_a_typed_value_and_long_values_use_positions() -> None:
    long_value = "x" * 70
    state = _state(
        [
            {
                "name": "chipset",
                "label": "Chipset",
                "kind": "select",
                "required": True,
                "allow_other": True,
                "choices": [{"value": "kt326"}, {"value": long_value}],
            }
        ]
    )
    first = flow.begin(state)
    assert first.prompt is not None and first.prompt.buttons == [
        [("kt326", "kt326"), (long_value, "#2")]
    ]
    assert "type another value" in first.prompt.text
    assert _confirmed(state, flow.answer(state, "kt999")) == {"chipset": "kt999"}
    again = _state(
        [
            {
                "name": "chipset",
                "label": "Chipset",
                "kind": "select",
                "required": True,
                "allow_other": True,
                "choices": [{"value": "kt326"}, {"value": long_value}],
            }
        ]
    )
    flow.begin(again)
    assert _confirmed(again, flow.answer(again, "#2")) == {"chipset": long_value}


def test_pick_or_type_with_an_unavailable_list_still_asks() -> None:
    state = _state(
        [
            {
                "name": "chipset",
                "label": "Chipset",
                "kind": "select",
                "required": True,
                "allow_other": True,
                "choices_source": "fn:release_package.chipsets",
            }
        ],
        choices=lambda _m, _s, _a: None,
    )
    first = flow.begin(state)
    assert first.prompt is not None and first.prompt.buttons == []
    assert "not available right now; type the value" in first.prompt.text
    assert _confirmed(state, flow.answer(state, "kt326")) == {"chipset": "kt326"}


UPLOAD = {
    "name": "plans",
    "label": "Plans",
    "kind": "upload",
    "multiple": True,
    "accept": [".json"],
}


def test_uploads_are_asked_when_the_channel_can_store_them() -> None:
    state = _state([{**UPLOAD, "required": True}], uploads=True)
    first = flow.begin(state)
    assert first.prompt is not None and "as documents" in first.prompt.text
    assert first.prompt.buttons == [[("Done", "/done")]]
    assert flow.current_upload(state) is not None
    assert (
        "Send at least one" not in (flow.answer(state, "hello").prompt or flow.FlowPrompt("")).text
    )
    flow.add_upload(state, "C:/store/a.json")
    flow.add_upload(state, "C:/store/b.json")
    assert "Received 2" in flow.prompt(state).text
    done = flow.answer(state, "/done")
    assert _confirmed(state, done) == {"plans": ["C:/store/a.json", "C:/store/b.json"]}
    required = _state([{**UPLOAD, "required": True}], uploads=True)
    flow.begin(required)
    assert (
        "Send at least one" in (flow.answer(required, "/done").prompt or flow.FlowPrompt("")).text
    )
    # An optional upload is not asked; 修改 on the card reaches it.
    optional = _state([UPLOAD], uploads=True)
    assert flow.begin(optional).kind == "ask" and optional.confirming
    flow.answer(optional, "run:edit")
    flow.answer(optional, "edit:0")
    assert flow.current_upload(optional) is not None
    flow.add_upload(optional, "C:/store/c.json")
    assert _confirmed(optional, flow.answer(optional, "/done")) == {"plans": ["C:/store/c.json"]}


def test_same_as_last_time_fills_the_identity_fields() -> None:
    """Last time's identity values are used and marked, never asked again
    (owner 2026-10-25); the card's 修改 or typed text changes them."""
    fields: list[dict[str, Any]] = [
        {
            "name": "company",
            "label": "Company",
            "kind": "text",
            "group": "identity",
            "required": True,
        },
        {"name": "chipset", "label": "Chipset", "kind": "text", "group": "identity"},
        {"name": "notes", "label": "Notes", "kind": "text"},
    ]
    preset = {"company": "Foxconn", "chipset": "kt326", "notes": "never offered"}
    state = _state(fields, preset=preset)
    card = flow.begin(state)
    assert card.prompt is not None and state.confirming
    assert "- Company：Foxconn（上次的值）" in card.prompt.text
    assert "- Chipset：kt326（上次的值）" in card.prompt.text
    assert "never offered" not in card.prompt.text
    changed = flow.answer(state, "Company Pegatron")
    assert changed.prompt is not None and "- Company：Pegatron\n" in changed.prompt.text
    assert flow.answer(state, "run:yes").arguments == {"company": "Pegatron", "chipset": "kt326"}
    # A required field still missing is asked, with last time's values named.
    asked = _state(
        [*fields, {"name": "repo", "label": "Repo", "kind": "text", "required": True}],
        preset=preset,
    )
    first = flow.begin(asked)
    assert first.prompt is not None and "Repo *" in first.prompt.text
    assert first.prompt.text.startswith("沿用上次的值：Company = Foxconn；Chipset = kt326")


# -- through the ingress ----------------------------------------------------------------


def test_a_toggle_edits_the_tapped_message(tmp_path: Path) -> None:
    transport = FileTransport([[update(1, OWNER, "/run release-validation-form")]], {})
    item, agent, _runner = ingress(tmp_path, transport)
    _install(agent, [PLANS])
    poll(item)
    transport.batches.append([_tap(2, OWNER, "pick:2", transport)])
    toggled = poll(item).deliveries[0]
    assert toggled.edit_message_id == 1 and toggled.replied
    edits = [payload for url, payload in transport.calls if url.endswith("/editMessageText")]
    assert edits[-1]["message_id"] == 1
    assert edits[-1]["reply_markup"]["inline_keyboard"][0][1] == {
        "text": flow.CHECK + "b.json",
        "callback_data": "pick:2",
    }


def test_documents_fill_an_upload_field_and_presets_are_remembered(tmp_path: Path) -> None:
    transport = FileTransport(
        [[update(1, OWNER, "/run release-validation-form")]], {"doc-1": b"{}", "doc-2": b"MZ"}
    )
    item, agent, _runner = ingress(tmp_path, transport)
    store = WorkflowUploadStore(tmp_path / "workspace")
    presets = IdentityPresets(tmp_path / "workspace")
    item.uploads, item.presets = store, presets
    manifest = _install(
        agent,
        [
            {
                "name": "company",
                "label": "Company",
                "kind": "text",
                "group": "identity",
                "required": True,
            },
            {
                "name": "package",
                "label": "Plan",
                "kind": "upload",
                "accept": [".json"],
                "required": True,
            },
        ],
    )
    poll(item)
    transport.batches.append([update(2, OWNER, "Foxconn")])
    asked = poll(item).deliveries[0]
    assert "as a document" in (asked.reply or "")
    transport.batches.append(
        [message(3, OWNER, document={"file_id": "doc-2", "file_name": "tool.exe", "file_size": 2})]
    )
    refused = poll(item).deliveries[0]
    assert "is not a .json file" in (refused.reply or "") and transport.downloads == []
    transport.batches.append(
        [message(4, OWNER, document={"file_id": "doc-1", "file_name": "plan.json", "file_size": 2})]
    )
    card = poll(item).deliveries[0]
    assert card.disposition == "answered" and "- Plan：plan.json" in (card.reply or "")
    transport.batches.append([_tap(5, OWNER, "run:yes", transport)])
    after = poll(item).deliveries[0]
    assert after.disposition == "routed" and after.outcome is not None
    stored = list((store.root).rglob("plan.json"))
    assert len(stored) == 1 and stored[0].read_bytes() == b"{}"
    assert presets.last("engineer", manifest) == {"company": "Foxconn"}
    # Next time the identity is not asked again; only the required upload is.
    transport.batches.append([update(6, OWNER, "/run release-validation-form")])
    offered = poll(item).deliveries[0]
    assert (offered.reply or "").startswith("沿用上次的值：Company = Foxconn")
    assert "as a document" in (offered.reply or "")
