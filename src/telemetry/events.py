"""Harness telemetry events, `aep.telemetry.v1` (docs/telemetry/AEP_ATLAS_TELEMETRY_CONTRACT.md).

One JSON object per event. Attributes are safe metadata only: names, ids,
counts, durations, codes. Never prompts, answers, retrieved text, tool
payloads or credentials. `sanitize` enforces that before an event is stored:
unknown value types are dropped, long strings cut, credential-shaped text and
content-like keys removed.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, Field

from common.assets import SECRET_PATTERN
from common.base import Contract

SCHEMA_VERSION: Literal["aep.telemetry.v1"] = "aep.telemetry.v1"
EventStatus = Literal["started", "succeeded", "failed", "skipped", "cancelled"]

# What `run_kind` names (contract v0.2 addition).
RUN_KINDS = (
    "conversation_turn",
    "workflow_run",
    "knowledge_query",
    "coding_change",
    "capability_call",
    "benchmark_run",
    "benchmark_grading",
)

# Recommended state names per harness (contract v0.2 addition), so state graphs
# compare across runs; `state` stays an open string.
STATES = {
    # Every domain on the shared Harness reports the same phases (unification
    # 2026-10-09), so state graphs compare across Coding, Workflow and Knowledge.
    "harness": (
        "collecting",
        "executing",
        "validating",
        "validated",
        "needs_input",
        "failed",
        "stopped",
    ),
    "conversation_turn": ("routing", "skill_selection", "model", "tool", "answer"),
    "workflow_run": ("step",),
}

MAX_STRING = 300
MAX_ATTRIBUTES = 40
MAX_LIST = 20
# Keys that would carry content rather than metadata are never stored.
_CONTENT_KEYS = re.compile(
    r"(prompt|message|text|content|answer|question|document|payload|body|script|"
    r"password|secret|token$|api_key|authorization|credential)",
    re.IGNORECASE,
)
# Token counts are metadata even though the word appears in their names.
_ALLOWED_KEYS = frozenset(
    {"input_tokens", "output_tokens", "context_tokens", "context_limit_tokens", "max_output_tokens"}
)


class TelemetryEvent(Contract):
    schema_version: Literal["aep.telemetry.v1"] = SCHEMA_VERSION
    event_id: str = Field(min_length=8, max_length=64)
    run_id: str = Field(min_length=1, max_length=128)
    trace_id: str = Field(min_length=1, max_length=128)
    span_id: str = Field(min_length=1, max_length=128)
    parent_span_id: str | None = None
    sequence: int = Field(ge=0, strict=True)
    timestamp: AwareDatetime
    event_type: str = Field(min_length=1, max_length=64)
    state: str | None = Field(default=None, max_length=64)
    status: EventStatus
    attributes: dict[str, Any] = Field(default_factory=dict)


def _clean(value: Any, depth: int = 0) -> Any:
    if value is None or isinstance(value, bool | int | float):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, str):
        cut = value[:MAX_STRING]
        return "[redacted]" if SECRET_PATTERN.search(cut) else cut
    if isinstance(value, list | tuple) and depth < 2:
        return [_clean(item, depth + 1) for item in list(value)[:MAX_LIST]]
    if isinstance(value, dict) and depth < 2:
        return sanitize(value, depth + 1)
    return None


def sanitize(attributes: dict[str, Any], depth: int = 0) -> dict[str, Any]:
    """Only metadata survives: bounded, typed, with content keys dropped."""
    kept: dict[str, Any] = {}
    for key, value in list(attributes.items())[:MAX_ATTRIBUTES]:
        name = str(key)[:64]
        if name not in _ALLOWED_KEYS and _CONTENT_KEYS.search(name):
            continue
        cleaned = _clean(value, depth)
        if cleaned is not None or value is None:
            kept[name] = cleaned
    return kept
