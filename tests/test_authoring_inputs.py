"""Bind only supplied user evidence into reusable Workflow declarations."""

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import JsonValue
from test_workflow_parameter_declaration import _manifest

from host_runtime.authoring_inputs import bind_supplied_inputs
from host_runtime.conversations import ConversationMessage


def _message(text: str, **extra: Any) -> ConversationMessage:
    return ConversationMessage(
        message_id="user-1",
        role="user",
        text=text,
        created_at=datetime.now(UTC),
        status="submitted",
        **extra,
    )


def _workbook(**extra: Any) -> dict[str, Any]:
    return {
        "name": "owner_mapping_excel",
        "label": "Owner mapping Excel",
        "kind": "file",
        "required": True,
        **extra,
    }


def test_original_user_quoted_workbook_path_becomes_required_default_with_origin() -> None:
    path = r"C:\Users\Chi_L\Documents\Owner Mapping.xlsx"
    manifest = _manifest([_workbook()])
    message = _message(f'對照表放在 "{path}"，請使用它。')
    bound, origins = bind_supplied_inputs(manifest, [message])
    assert bound.parameters[0].default == path
    assert bound.parameters[0].file_mode == "input"
    assert bound.parameters[0].required is True
    assert bound.metadata == manifest.metadata and bound.steps == manifest.steps
    assert origins["owner_mapping_excel"] == {
        "value": path,
        "origin": "message",
        "source_id": "user-1",
        "recorded_at": message.created_at.isoformat(),
    }
    assert manifest.parameters[0].default is None


def test_pdf_sop_is_not_confused_with_the_attached_workbook() -> None:
    attachments = (
        {"name": "SOP.pdf", "kind": "pdf", "path": "C:/uploads/SOP.pdf"},
        {"name": "Owners.xlsx", "kind": "xlsx", "path": "C:/uploads/Owners.xlsx"},
    )
    bound, origins = bind_supplied_inputs(
        _manifest([_workbook()]), [_message("使用附件", attachments=attachments)]
    )
    assert bound.parameters[0].default == "C:/uploads/Owners.xlsx"
    assert origins["owner_mapping_excel"]["origin"] == "attachment"
    assert origins["owner_mapping_excel"]["source_id"] == "user-1"


def test_two_matching_workbooks_are_ambiguous_and_neither_is_guessed() -> None:
    bound, origins = bind_supplied_inputs(
        _manifest([_workbook()]),
        [],
        current_text="使用附件",
        current_attachments=[{"path": "C:/one.xlsx"}, {"path": "C:/two.xlsx"}],
    )
    assert bound.parameters[0].default is None and origins == {}


def test_only_actual_user_values_bind_and_privileged_confirmation_stays_unfilled() -> None:
    manifest = _manifest(
        [
            {"name": "company", "label": "Company", "kind": "text", "required": True},
            {"name": "send", "label": "Send", "kind": "boolean", "confirm": True},
        ]
    )
    assistant = ConversationMessage(
        message_id="answer-1",
        role="assistant",
        text="company=Invented",
        created_at=datetime.now(UTC),
        status="answered",
    )
    before = datetime.now(UTC)
    bound, origins = bind_supplied_inputs(
        manifest, [assistant], current_text="company=Foxconn send=true"
    )
    after = datetime.now(UTC)
    assert bound.parameters[0].default == "Foxconn"
    assert bound.parameters[1].default is None
    assert origins == {
        "company": {
            "value": "Foxconn",
            "origin": "message",
            "source_id": "current",
            "recorded_at": origins["company"]["recorded_at"],
        }
    }
    stamp = origins["company"]["recorded_at"]
    assert isinstance(stamp, str)
    assert before <= datetime.fromisoformat(stamp) <= after


def test_output_file_and_untyped_file_are_not_assumed_to_be_input_attachments() -> None:
    manifest = _manifest(
        [_workbook(file_mode="output"), {"name": "other", "label": "Other", "kind": "file"}]
    )
    bound, origins = bind_supplied_inputs(
        manifest, [], current_attachments=[{"path": "C:/one.xlsx"}]
    )
    assert bound == manifest and origins == {}


def test_named_values_and_doubled_windows_separators_are_kept_exactly() -> None:
    path = r"C:\\Data\\Owners.xlsx"
    bound, origins = bind_supplied_inputs(
        _manifest([_workbook()]), [], current_text=f'owner_mapping_excel="{path}"'
    )
    assert bound.parameters[0].default == path
    assert origins["owner_mapping_excel"]["value"] == path


def test_remembered_user_path_survives_eviction_of_every_source_message() -> None:
    remembered: dict[str, dict[str, JsonValue]] = {
        "owner_mapping_excel": {
            "value": "C:/Data/Owners.xlsx",
            "origin": "attachment",
            "source_id": "original-user",
        }
    }
    bound, origins = bind_supplied_inputs(_manifest([_workbook()]), [], remembered=remembered)
    assert bound.parameters[0].default == "C:/Data/Owners.xlsx"
    assert bound.parameters[0].file_mode == "input"
    assert origins == remembered


def test_new_user_file_reference_overrides_remembered_path() -> None:
    bound, origins = bind_supplied_inputs(
        _manifest([_workbook()]),
        [],
        current_text='改用 "C:/Data/NewOwners.xlsx"',
        remembered={
            "owner_mapping_excel": {
                "value": "C:/Data/OldOwners.xlsx",
                "origin": "message",
                "source_id": "old-user",
            }
        },
    )
    assert bound.parameters[0].default == "C:/Data/NewOwners.xlsx"
    assert origins["owner_mapping_excel"]["source_id"] == "current"


def test_remembered_values_respect_parameter_types_and_privileged_boundaries() -> None:
    manifest = _manifest(
        [
            {"name": "send", "label": "Send", "kind": "boolean", "confirm": True},
            {"name": "package", "label": "Package", "kind": "upload"},
            _workbook(file_mode="output"),
            {"name": "count", "label": "Count", "kind": "integer"},
        ]
    )
    values: dict[str, JsonValue] = {
        "send": True,
        "package": "C:/file.xlsx",
        "owner_mapping_excel": "C:/out.xlsx",
        "count": "invalid-number",
    }
    remembered = {
        name: {"value": value, "origin": "message", "source_id": "old-user"}
        for name, value in values.items()
    }
    bound, origins = bind_supplied_inputs(manifest, [], remembered=remembered)
    assert bound == manifest and origins == {}


@pytest.mark.parametrize("named", [True, False])
@pytest.mark.parametrize("newer_message", [True, False])
def test_only_newer_user_evidence_overrides_a_remembered_form_answer(
    named: bool, newer_message: bool
) -> None:
    old_path, form_path = "C:/Data/Message.xlsx", "C:/Data/Form.xlsx"
    text = f'owner_mapping_excel="{old_path}"' if named else f'使用 "{old_path}"'
    timestamp = "2026-11-09T13:00:00+00:00" if newer_message else "2026-11-09T11:00:00+00:00"
    message = _message(text).model_copy(update={"created_at": datetime.fromisoformat(timestamp)})
    remembered: dict[str, dict[str, JsonValue]] = {
        "owner_mapping_excel": {
            "value": form_path,
            "origin": "form",
            "source_id": "form",
            "recorded_at": "2026-11-09T12:00:00+00:00",
        }
    }
    bound, origins = bind_supplied_inputs(
        _manifest([_workbook()]), [message], remembered=remembered
    )
    assert bound.parameters[0].default == (old_path if newer_message else form_path)
    if newer_message:
        assert origins["owner_mapping_excel"]["recorded_at"] == timestamp
        assert origins["owner_mapping_excel"]["source_id"] == "user-1"
    else:
        assert origins == remembered


def test_old_file_notes_do_not_make_a_fresh_replacement_ambiguous() -> None:
    old = _message('使用 "C:/Data/Old.xlsx"').model_copy(
        update={"created_at": datetime.fromisoformat("2026-11-09T11:00:00+00:00")}
    )
    fresh = _message('改用 "C:/Data/Fresh.xlsx"').model_copy(
        update={
            "message_id": "user-2",
            "created_at": datetime.fromisoformat("2026-11-09T13:00:00+00:00"),
        }
    )
    bound, origins = bind_supplied_inputs(
        _manifest([_workbook()]),
        [old, fresh],
        remembered={
            "owner_mapping_excel": {
                "value": "C:/Data/Form.xlsx",
                "origin": "form",
                "source_id": "form",
                "recorded_at": "2026-11-09T12:00:00+00:00",
            }
        },
    )
    assert bound.parameters[0].default == "C:/Data/Fresh.xlsx"
    assert origins["owner_mapping_excel"]["source_id"] == "user-2"
