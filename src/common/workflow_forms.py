"""Generated run forms from one Workflow parameter declaration.

Agent Web, the schedule form, the Telegram question flow and the Agent tool
schema all derive their fields from `WorkflowParameter`, so a contributor
declares a Workflow once (rs_workflow_system `PARAMS_SCHEMA` + `x-ui`). This
module is pure: it reads a manifest and returns plain data.
"""

from __future__ import annotations

from typing import Any

from common.assets import ParameterChannel, WorkflowManifest, WorkflowParameter

IDENTITY_GROUP = "identity"


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
    return data


def form_fields(manifest: WorkflowManifest, channel: ParameterChannel) -> list[dict[str, Any]]:
    return [form_field(field) for field in ordered_fields(manifest, channel)]


def agent_fields(manifest: WorkflowManifest) -> tuple[WorkflowParameter, ...]:
    """Fields a model may fill: agent-channel runtime fields, never privileged.

    A privileged field (`confirm`) such as "send mail" stays a person's
    choice; static settings and secrets are never run fields at all.
    """
    return tuple(field for field in ordered_fields(manifest, "agent") if not field.confirm)


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
