"""Bind supplied user evidence to declarations; never search for missing inputs."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import PurePosixPath, PureWindowsPath

from pydantic import JsonValue

from common.assets import (
    WorkflowManifest,
    WorkflowParameter,
    parameter_value_problem,
    reject_embedded_secrets,
)
from common.workflow_run_form import prefill_from_text
from host_runtime.conversations import ConversationMessage

MAX_BOUND_INPUTS = 64
MAX_REFERENCE_LENGTH = 4096
_QUOTED = re.compile(r"""["'`]([^"'`\r\n]+)["'`]""")
_WORKBOOK_SUFFIXES = frozenset({".xlsx", ".xls", ".xlsm", ".xlsb"})


def _absolute(path: str) -> bool:
    return PureWindowsPath(path).is_absolute() or PurePosixPath(path).is_absolute()


def _suffixes(field: WorkflowParameter) -> set[str]:
    if field.accept:
        return {"." + extension.strip().casefold().lstrip(".") for extension in field.accept}
    description = f"{field.name} {field.label}".casefold()
    if any(word in description for word in ("excel", "workbook", "試算表", "活頁簿")):
        return set(_WORKBOOK_SUFFIXES)
    return {
        suffix for suffix in (".xlsx", ".xls", ".pdf", ".docx", ".csv") if suffix in description
    }


def _safe(value: JsonValue) -> bool:
    if isinstance(value, str) and len(value) > MAX_REFERENCE_LENGTH:
        return False
    try:
        reject_embedded_secrets({"value": value})
    except ValueError:
        return False
    return True


def _timestamp(value: JsonValue) -> datetime | None:
    if not isinstance(value, str) or len(value) > 80:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _newer(record: Mapping[str, JsonValue], previous: Mapping[str, JsonValue]) -> bool:
    previous_time = _timestamp(previous.get("recorded_at"))
    current_time = _timestamp(record.get("recorded_at"))
    return previous_time is None or (current_time is not None and current_time > previous_time)


def bind_supplied_inputs(
    manifest: WorkflowManifest,
    messages: Sequence[ConversationMessage],
    current_text: str = "",
    current_attachments: Sequence[dict[str, str]] = (),
    *,
    remembered: Mapping[str, dict[str, JsonValue]] | None = None,
) -> tuple[WorkflowManifest, dict[str, dict[str, JsonValue]]]:
    """Return defaults plus provenance from actual user messages/attachments.

    Exact declared name/value pairs use the shared form parser. An unnamed
    file reference binds only when its declared suffix/type identifies one
    supplied candidate. Files are references, never opened here; run validation
    and Bridge ownership/root checks still apply. Conflicting unnamed files
    remain unanswered. Validated remembered bindings survive history eviction;
    new user evidence takes precedence. Privileged, upload and declared output
    fields stay out.
    """
    fields = {
        field.name: field
        for field in manifest.parameters
        if field.scope == "runtime"
        and not field.confirm
        and field.kind != "upload"
        and field.file_mode != "output"
    }
    stored: dict[str, dict[str, JsonValue]] = {}
    for name, field in fields.items():
        record = (remembered or {}).get(name)
        if record is None or "value" not in record:
            continue
        value = record["value"]
        origin, source_id = record.get("origin"), record.get("source_id")
        if (
            not isinstance(origin, str)
            or not origin.strip()
            or not isinstance(source_id, str)
            or not source_id.strip()
            or not all(_safe(item) for item in (value, origin, source_id))
            or parameter_value_problem(field, value) is not None
        ):
            continue
        stored[name] = {"value": value, "origin": origin, "source_id": source_id}
        if _timestamp(record.get("recorded_at")) is not None:
            stored[name]["recorded_at"] = record["recorded_at"]
    evidence = [
        (message.message_id, message.text, message.attachments, message.created_at)
        for message in messages[-100:]
        if message.role == "user"
    ]
    if current_text or current_attachments:
        evidence.append(("current", current_text, tuple(current_attachments), datetime.now(UTC)))
    bound: dict[str, dict[str, JsonValue]] = {}
    references: dict[str, dict[str, JsonValue]] = {}
    for source_id, text, attachments, created_at in evidence:
        recorded_at = (
            created_at.replace(tzinfo=UTC).isoformat()
            if created_at.tzinfo is None
            else created_at.isoformat()
        )
        for name, value in prefill_from_text(manifest, text).items():
            if name in fields and _safe(value):
                candidate: dict[str, JsonValue] = {
                    "value": value,
                    "origin": "message",
                    "source_id": source_id,
                    "recorded_at": recorded_at,
                }
                if _newer(candidate, bound.get(name, stored.get(name, {}))):
                    bound[name] = candidate
        for raw in _QUOTED.findall(text):
            path = PureWindowsPath(raw)
            if _absolute(raw) and path.suffix and _safe(raw):
                candidate = {
                    "value": raw,
                    "origin": "message",
                    "source_id": source_id,
                    "recorded_at": recorded_at,
                }
                if _newer(candidate, references.get(raw, {})):
                    references[raw] = candidate
        for attachment in attachments[:100]:
            path_value = attachment.get("path", "")
            path = PureWindowsPath(path_value)
            if _absolute(path_value) and path.suffix and _safe(path_value):
                candidate = {
                    "value": path_value,
                    "origin": "attachment",
                    "source_id": source_id,
                    "recorded_at": recorded_at,
                }
                if _newer(candidate, references.get(path_value, {})):
                    references[path_value] = candidate
    for name, field in fields.items():
        if field.kind != "file" or field.multiple or name in bound:
            continue
        suffixes = _suffixes(field)
        matching = [
            reference
            for path, reference in references.items()
            if PureWindowsPath(path).suffix.casefold() in suffixes
            and _newer(reference, stored.get(name, {}))
        ]
        if len(matching) == 1:
            bound[name] = matching[0]
    merged = {**stored, **bound}
    provenance = {name: merged[name] for name in fields if name in merged}  # Manifest order.
    provenance = dict(list(provenance.items())[:MAX_BOUND_INPUTS])
    parameters = []
    for field in manifest.parameters:
        if field.name not in provenance:
            parameters.append(field.model_dump(mode="json"))
            continue
        data = field.model_dump(mode="json")
        data["default"] = provenance[field.name]["value"]
        if field.kind == "file":
            data["file_mode"] = "input"
        parameters.append(data)
    data = manifest.model_dump(mode="json")
    data["parameters"] = parameters
    return WorkflowManifest.model_validate(data), provenance
