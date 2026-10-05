"""Validate declared runtime fields without granting Workflow execution rights."""

from __future__ import annotations

from collections.abc import Mapping

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
            if field.required:
                raise WorkflowParameterError(f"{name} is required")
            if field.default is not None:
                # A declared default is part of the contract; every channel
                # (web, schedule, Telegram, Agent) gets the same value.
                checked[name] = field.default
            continue
        _validate_value(field, arguments[name])
    return checked


def _validate_value(field: WorkflowParameter, value: JsonValue) -> None:
    problem = parameter_value_problem(field, value)
    if problem:
        raise WorkflowParameterError(f"{field.name} {problem}")
