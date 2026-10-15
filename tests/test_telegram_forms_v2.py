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

PLANS = {
    "name": "plans",
    "label": "Plans",
    "kind": "select",
    "multiple": True,
    "choices": [{"value": "a.json"}, {"value": "b.json"}, {"value": "c.json"}],
}


def _state(fields: list[dict[str, Any]], **kwargs: Any) -> flow.FlowState:
    started = flow.start(_manifest(fields), "read", **kwargs)
    assert isinstance(started, flow.FlowState)
    return started


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
    assert done.kind == "ready" and done.arguments == {"plans": ["a.json"]}
    # Typing still works.
    typed = _state([PLANS])
    flow.begin(typed)
    assert flow.answer(typed, "b.json, c.json").arguments == {"plans": ["b.json", "c.json"]}


def test_a_required_multi_select_needs_one_tick_and_many_choices_are_capped() -> None:
    state = _state([{**PLANS, "required": True}])
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
    assert flow.answer(state, "kt999").arguments == {"chipset": "kt999"}
    again = _state(
        [
            {
                "name": "chipset",
                "label": "Chipset",
                "kind": "select",
                "allow_other": True,
                "choices": [{"value": "kt326"}, {"value": long_value}],
            }
        ]
    )
    flow.begin(again)
    assert flow.answer(again, "#2").arguments == {"chipset": long_value}


def test_pick_or_type_with_an_unavailable_list_still_asks() -> None:
    state = _state(
        [
            {
                "name": "chipset",
                "label": "Chipset",
                "kind": "select",
                "allow_other": True,
                "choices_source": "fn:release_package.chipsets",
            }
        ],
        choices=lambda _m, _s, _a: None,
    )
    first = flow.begin(state)
    assert first.prompt is not None and first.prompt.buttons == []
    assert "not available right now; type the value" in first.prompt.text
    assert flow.answer(state, "kt326").arguments == {"chipset": "kt326"}


UPLOAD = {
    "name": "plans",
    "label": "Plans",
    "kind": "upload",
    "multiple": True,
    "accept": [".json"],
}


def test_uploads_are_asked_when_the_channel_can_store_them() -> None:
    state = _state([UPLOAD], uploads=True)
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
    assert done.kind == "ready"
    assert done.arguments == {"plans": ["C:/store/a.json", "C:/store/b.json"]}
    required = _state([{**UPLOAD, "required": True}], uploads=True)
    flow.begin(required)
    assert (
        "Send at least one" in (flow.answer(required, "/done").prompt or flow.FlowPrompt("")).text
    )


def test_same_as_last_time_fills_the_identity_fields() -> None:
    fields = [
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
    first = flow.begin(state)
    assert first.prompt is not None and "same as last time?" in first.prompt.text
    assert "Company: Foxconn" in first.prompt.text and "never offered" not in first.prompt.text
    assert first.prompt.buttons == [[("Yes", "preset:yes"), ("Change", "preset:no")]]
    notes = flow.answer(state, "preset:yes")
    assert notes.prompt is not None and "Notes" in notes.prompt.text
    assert flow.answer(state, "/skip").arguments == {"company": "Foxconn", "chipset": "kt326"}
    change = _state(fields, preset=preset)
    flow.begin(change)
    company = flow.answer(change, "preset:no")
    assert company.prompt is not None and "Company *" in company.prompt.text
    assert _state(fields).asking_preset is False


# -- through the ingress ----------------------------------------------------------------


def test_a_toggle_edits_the_tapped_message(tmp_path: Path) -> None:
    transport = FileTransport([[update(1, OWNER, "/run release-validation-form")]], {})
    item, agent, _runner = ingress(tmp_path, transport)
    _install(agent, [PLANS])
    poll(item)
    transport.batches.append([_tap(2, OWNER, "pick:2")])
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
            {"name": "company", "label": "Company", "kind": "text", "group": "identity"},
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
    after = poll(item).deliveries[0]
    if after.disposition == "answered":  # effect confirmation
        transport.batches.append([_tap(5, OWNER, "run:yes")])
        after = poll(item).deliveries[0]
    assert after.disposition == "routed" and after.outcome is not None
    stored = list((store.root).rglob("plan.json"))
    assert len(stored) == 1 and stored[0].read_bytes() == b"{}"
    assert presets.last("engineer", manifest) == {"company": "Foxconn"}
    # Next time the flow offers the same identity first.
    transport.batches.append([update(6, OWNER, "/run release-validation-form")])
    offered = poll(item).deliveries[0]
    assert "same as last time?" in (offered.reply or "")
