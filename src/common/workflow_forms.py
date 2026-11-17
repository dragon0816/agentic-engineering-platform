"""Generated run forms from one Workflow parameter declaration.

Agent Web, the schedule form, the Telegram question flow and the Agent tool
schema all derive their fields from `WorkflowParameter`, so a contributor
declares a Workflow once (rs_workflow_system `PARAMS_SCHEMA` + `x-ui`). This
module is pure: it reads a manifest and returns plain data.
"""

from __future__ import annotations

import re
from typing import Any

from common.assets import ParameterChannel, WorkflowManifest, WorkflowParameter

IDENTITY_GROUP = "identity"
#: The derived false choice of a boolean without a declared one.
FALSE_PREFIX = "不要："
_QUESTION_END = re.compile(r"[\s?？]+$")
_LABEL_HEAD = re.compile(r"\s*[（(].*$")
_TRAILING = re.compile(r"[\s。.!！?？~～吧啦喔哦]+$")


def boolean_labels(field: WorkflowParameter) -> tuple[str, str]:
    """A boolean's (true, false) choices in plain words (owner 2026-10-25).

    The declaration's `true_label` / `false_label` when present; otherwise the
    true choice is the field's label (without a trailing question mark) and
    the false one 「不要：<label>」. Never a bare Yes/No.
    """
    head = _QUESTION_END.sub("", field.label) or field.label
    return (field.true_label or head, field.false_label or FALSE_PREFIX + head)


def boolean_label(field: WorkflowParameter, value: bool) -> str:
    true, false = boolean_labels(field)
    return true if value else false


def _label_keys(label: str) -> set[str]:
    """A choice label and its head before a parenthesis: 「只看計畫（不寫入）」
    is also 「只看計畫」."""
    keys = {label.strip().casefold()}
    head = _LABEL_HEAD.sub("", label).strip()
    if head:
        keys.add(head.casefold())
    return keys


def boolean_from_label(field: WorkflowParameter, text: str) -> bool | None:
    """True or False when `text` names one of the field's two choices (the
    whole label, its head before a parenthesis, or the start of only one of
    them, at least two characters); else None."""
    said = _TRAILING.sub("", text.strip()).strip().casefold()
    if not said:
        return None
    true, false = boolean_labels(field)
    for value, label in ((True, true), (False, false)):
        if said in _label_keys(label):
            return value
    if len(said) < 2:
        return None
    starts = [
        value
        for value, label in ((True, true), (False, false))
        if label.strip().casefold().startswith(said)
    ]
    return starts[0] if len(starts) == 1 else None


def ordered_fields(
    manifest: WorkflowManifest, channel: ParameterChannel
) -> tuple[WorkflowParameter, ...]:
    """Runtime fields shown on `channel`: identity group first, then by order.

    A field without `order` keeps its position in the manifest, which the
    contract already requires to put depended-on fields first.
    """
    indexed = [
        (index, field)
        for index, field in enumerate(manifest.parameters)
        if field.scope == "runtime" and channel in field.channels
    ]
    indexed.sort(
        key=lambda item: (
            item[1].group != IDENTITY_GROUP,
            item[1].order if item[1].order is not None else item[0],
            item[0],
        )
    )
    return tuple(field for _, field in indexed)


def form_field(field: WorkflowParameter) -> dict[str, Any]:
    """One field as every generated interface reads it.

    Keeps the legacy keys (for older renderers) and adds normalized ones:
    labelled `choices` (from `choices` or the `options` shorthand) and one
    `help` text (from `help` or `description`).
    """
    data = field.model_dump(mode="json")
    data.update(
        {
            "choices": [
                {"value": value, "label": label}
                for value, label in (
                    [(item.value, item.label or item.value) for item in field.choices]
                    or [(value, value) for value in field.options]
                )
            ],
            "help": field.help or field.description or "",
            "default": field.default,
            "choices_source": field.choices_source,
            "allow_other": field.allow_other,
            "needs": list(field.needs),
            "multiple": field.multiple,
            "accept": list(field.accept),
            "group": field.group,
            "examples": list(field.examples),
            "pattern": field.pattern,
            "min_length": field.min_length,
            "confirm": field.confirm,
        }
    )
    if field.kind == "boolean":
        # The two choices every interface shows (declared or derived).
        data["true_label"], data["false_label"] = boolean_labels(field)
    return data


def form_fields(manifest: WorkflowManifest, channel: ParameterChannel) -> list[dict[str, Any]]:
    return [form_field(field) for field in ordered_fields(manifest, channel)]


def agent_fields(manifest: WorkflowManifest) -> tuple[WorkflowParameter, ...]:
    """All declared agent-channel runtime inputs, including execution choices.

    Legacy `confirm` is presentation metadata, not execution authorization.
    Static settings and secret references remain outside run arguments.
    """
    return ordered_fields(manifest, "agent")


def _property_schema(field: WorkflowParameter) -> dict[str, Any]:
    kind = field.kind
    item: dict[str, Any]
    if kind in ("integer", "number"):
        item = {"type": kind}
        if field.minimum is not None:
            item["minimum"] = field.minimum
        if field.maximum is not None:
            item["maximum"] = field.maximum
    elif kind == "boolean":
        item = {"type": "boolean"}
    elif kind == "date":
        item = {"type": "string", "format": "date"}
    elif kind == "emails":
        item = {"type": "string", "format": "email"}
    else:
        item = {"type": "string", "minLength": max(1, field.min_length or 1)}
        if field.pattern:
            item["pattern"] = field.pattern
        if field.choice_values and field.choices_source is None and not field.allow_other:
            item["enum"] = list(field.choice_values)
    schema = (
        {"type": "array", "items": item}
        if field.multiple or kind in ("text_list", "emails")
        else item
    )
    description = field.label + (
        f": {field.help or field.description}" if field.help or field.description else ""
    )
    if kind == "boolean" and (field.true_label or field.false_label):
        true, false = boolean_labels(field)
        description += f" (true: {true}; false: {false})"
    schema["description"] = description
    if field.default is not None:
        schema["default"] = field.default
    return schema


def agent_tool_schema(manifest: WorkflowManifest) -> dict[str, Any]:
    """A closed JSON Schema for the model's tool call, from the declaration."""
    fields = agent_fields(manifest)
    return {
        "type": "object",
        "properties": {field.name: _property_schema(field) for field in fields},
        "required": [field.name for field in fields if field.required],
        "additionalProperties": False,
    }


def settings_fields(manifest: WorkflowManifest) -> list[dict[str, Any]]:
    """The settings page form: `scope: static` fields in declared order.

    Settings adapt a Workflow to one computer and are never asked at run time,
    so every generated run interface leaves them out.
    """
    indexed = [
        (index, field) for index, field in enumerate(manifest.parameters) if field.scope == "static"
    ]
    indexed.sort(
        key=lambda item: (
            item[1].order if item[1].order is not None else item[0],
            item[0],
        )
    )
    return [form_field(field) for _, field in indexed]
