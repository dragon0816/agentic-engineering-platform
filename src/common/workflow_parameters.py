"""Validate declared runtime fields without granting Workflow execution rights."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date

from pydantic import JsonValue

from common.assets import WorkflowManifest, WorkflowParameter


class WorkflowParameterError(ValueError):
    """A named field is absent or has the wrong declared type."""


def validate_run_parameters(
    manifest: WorkflowManifest, arguments: Mapping[str, JsonValue]
) -> dict[str, JsonValue]:
    """Check one installed manifest's runtime schema before dispatch.

    Older manifests have no field schema and retain their existing input
    contract validation in the Workflow's deterministic capability handlers.
    Static fields are configuration, never values supplied by a run.
    """
    fields = {field.name: field for field in manifest.parameters if field.scope == "runtime"}
    if not manifest.parameters:
        return dict(arguments)
    for name in arguments:
        if name not in fields:
            raise WorkflowParameterError(f"{name} is not a declared runtime parameter")
    for name, field in fields.items():
        if name not in arguments:
            if field.required:
                raise WorkflowParameterError(f"{name} is required")
            continue
        _validate_value(field, arguments[name])
    return dict(arguments)


def _validate_value(field: WorkflowParameter, value: JsonValue) -> None:
    name = field.name
    if field.kind in ("text", "select"):
        if not isinstance(value, str) or not value.strip():
            raise WorkflowParameterError(f"{name} must be nonempty text")
        if field.kind == "select" and value not in field.options:
            raise WorkflowParameterError(f"{name} must be a declared option")
    elif field.kind == "integer":
        if type(value) is not int:
            raise WorkflowParameterError(f"{name} must be a whole number")
        if field.minimum is not None and value < field.minimum:
            raise WorkflowParameterError(f"{name} is below its minimum")
        if field.maximum is not None and value > field.maximum:
            raise WorkflowParameterError(f"{name} is above its maximum")
    elif field.kind == "boolean":
        if type(value) is not bool:
            raise WorkflowParameterError(f"{name} must be true or false")
    elif field.kind == "date":
        if not isinstance(value, str):
            raise WorkflowParameterError(f"{name} must be a YYYY-MM-DD date")
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise WorkflowParameterError(f"{name} must be a YYYY-MM-DD date") from None
        if parsed.isoformat() != value:
            raise WorkflowParameterError(f"{name} must be a YYYY-MM-DD date")
