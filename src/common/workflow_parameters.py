"""Validate declared runtime fields without granting Workflow execution rights."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from pydantic import JsonValue

from common.assets import WorkflowManifest, WorkflowParameter, parameter_value_problem


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
    checked = dict(arguments)
    for name, field in fields.items():
        if name not in arguments:
            if field.default is not None:
                # A declared default is part of the contract; every channel
                # (web, schedule, Telegram, Agent) gets the same value.
                _validate_value(field, field.default)
                checked[name] = field.default
            elif field.required:
                raise WorkflowParameterError(f"{name} is required")
            continue
        _validate_value(field, arguments[name])
    return checked


def _validate_value(field: WorkflowParameter, value: JsonValue) -> None:
    problem = parameter_value_problem(field, value)
    if problem:
        raise WorkflowParameterError(f"{field.name} {problem}")
    if field.kind == "file":
        # These checks do not grant access: Bridge roots/ownership still govern
        # actual reads. Uploads retain their separate store/authorization checks.
        values = value if field.multiple else [value]
        assert isinstance(values, list | tuple)
        for item in values:
            assert isinstance(item, str)
            path = Path(item)
            if path.is_dir():
                raise WorkflowParameterError(f"{field.name} must be a file, not a directory")
            if field.file_mode == "input" and not path.is_file():
                raise WorkflowParameterError(f"{field.name} must refer to an existing file")
            accepted = {"." + extension.strip().lower().lstrip(".") for extension in field.accept}
            if accepted and path.suffix.lower() not in accepted:
                raise WorkflowParameterError(f"{field.name} must be an accepted file type")


def static_fields(manifest: WorkflowManifest) -> tuple[WorkflowParameter, ...]:
    """The per-install settings a Workflow declares (`scope: static`)."""
    return tuple(field for field in manifest.parameters if field.scope == "static")


def validate_static_settings(
    manifest: WorkflowManifest,
    values: Mapping[str, JsonValue],
    *,
    complete: bool,
) -> dict[str, JsonValue]:
    """Check one install's settings for a Workflow and apply declared defaults.

    Settings adapt a Workflow to a person's computer (for example where its
    reference data lives); they are set once on the settings page and never
    supplied by a run. `complete` requires every required setting, as a run
    does; saving a partly filled page does not.
    """
    fields = {field.name: field for field in static_fields(manifest)}
    for name in values:
        if name not in fields:
            raise WorkflowParameterError(f"{name} is not a declared setting")
    checked: dict[str, JsonValue] = {}
    for name, field in fields.items():
        if name in values and values[name] is not None:
            _validate_value(field, values[name])
            checked[name] = values[name]
        elif field.default is not None:
            _validate_value(field, field.default)
            checked[name] = field.default
        elif complete and field.required:
            raise WorkflowParameterError(f"{name} is required")
    return checked
