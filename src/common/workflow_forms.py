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
        (index, field) for index, field in enumerate(manifest.parameters)
        if field.scope == "runtime" and channel in field.channels
    ]
    indexed.sort(key=lambda item: (
        item[1].group != IDENTITY_GROUP,
        item[1].order if item[1].order is not None else item[0],
        item[0],
    ))
    return tuple(field for _, field in indexed)


def form_field(field: WorkflowParameter) -> dict[str, Any]:
    """One field as every generated interface reads it.

    Keeps the legacy keys (for older renderers) and adds normalized ones:
    labelled `choices` (from `choices` or the `options` shorthand) and one
    `help` text (from `help` or `description`).
    """
    data = field.model_dump(mode="json")
    data.update({
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
        "needs": list(field.needs),
        "multiple": field.multiple,
        "accept": list(field.accept),
        "group": field.group,
        "examples": list(field.examples),
        "pattern": field.pattern,
        "min_length": field.min_length,
        "confirm": field.confirm,
    })
    return data


def form_fields(manifest: WorkflowManifest, channel: ParameterChannel) -> list[dict[str, Any]]:
    return [form_field(field) for field in ordered_fields(manifest, channel)]
