"""A small deterministic JSON transformation used by the first Harness proof."""

from __future__ import annotations

import json
from typing import Literal

from pydantic import JsonValue

from common.base import Contract, Text
from harness.contracts import CodingHarnessRequest, ValidationFailure
from harness.workspace import BoundedWorkspace


class FieldRule(Contract):
    target: Text
    source: Text
    operations: tuple[Literal["strip", "lower", "integer"], ...] = ()


class JsonTransform(Contract):
    fields: tuple[FieldRule, ...]


def _apply_operation(value: JsonValue, operation: str) -> JsonValue:
    if operation == "strip":
        if not isinstance(value, str):
            raise ValueError("strip requires text")
        return value.strip()
    if operation == "lower":
        if not isinstance(value, str):
            raise ValueError("lower requires text")
        return value.lower()
    if operation == "integer":
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError("integer requires integer text")
        return int(value)
    raise ValueError("unknown operation")


def transform(recipe: JsonTransform, value: JsonValue) -> JsonValue:
    if not isinstance(value, list):
        raise ValueError("input must be a list of records")
    output: list[JsonValue] = []
    for raw in value:
        if not isinstance(raw, dict):
            raise ValueError("each input record must be an object")
        record: dict[str, JsonValue] = {}
        for rule in recipe.fields:
            if rule.source not in raw:
                raise ValueError("source field missing")
            field = raw[rule.source]
            for operation in rule.operations:
                field = _apply_operation(field, operation)
            record[rule.target] = field
        output.append(record)
    return output


def validate_json_transform(
    workspace: BoundedWorkspace, request: CodingHarnessRequest
) -> tuple[ValidationFailure, ...]:
    payload = workspace.read(request.artifact_path)
    if payload is None:
        return (
            ValidationFailure(
                case="artifact", code="artifact_missing", message="Transformation is missing"
            ),
        )
    try:
        recipe = JsonTransform.model_validate_json(payload)
    except (ValueError, json.JSONDecodeError):
        return (
            ValidationFailure(
                case="artifact", code="invalid_artifact", message="Transformation is invalid"
            ),
        )
    failures: list[ValidationFailure] = []
    for case in request.cases:
        try:
            observed = transform(recipe, case.input)
        except (TypeError, ValueError):
            failures.append(
                ValidationFailure(
                    case=case.name,
                    code="transform_error",
                    message="Transformation could not process the case",
                    expected=case.expected,
                )
            )
            continue
        if observed != case.expected:
            failures.append(
                ValidationFailure(
                    case=case.name,
                    code="output_mismatch",
                    message="Observed output did not match the committed expectation",
                    expected=case.expected,
                    observed=observed,
                )
            )
    return tuple(failures)
