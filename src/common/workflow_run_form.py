"""A person's "run X" in a chat becomes that Workflow's generated run form.

Owner finding 2026-10-15: asked in Agent Web or Telegram to run an installed
Workflow, the model answered in prose ("please give release_repo_url, ...")
or listed Workflows, instead of showing the form the Workflow declares. The
form is drawn from the Workflow's parameter declaration everywhere, so a chat
request hands the person that same form (Agent Web) or question flow
(Telegram) rather than letting a model collect or invent the values.

This module is pure. It recognizes an explicit run request for an installed
Workflow, keeps the run values a person (or, for agent fields only, the
model) already gave as prefill, names required settings that are not set,
and describes the hand-off as a plain `workflow_form` offer the channels
render. See docs/phases/CHAT_WORKFLOW_FORMS.md.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from common.assets import (
    ParameterChannel,
    WorkflowManifest,
    WorkflowParameter,
    parameter_value_problem,
    reject_embedded_secrets,
)
from common.workflow_forms import agent_fields, ordered_fields
from common.workflow_parameters import static_fields

#: The data key a host tool outcome carries the offer under.
OFFER_KEY = "workflow_form"
#: The conversation tool a model calls to hand a person a Workflow's form.
FORM_TOOL = "workflows__run_form"
#: What the conversation prompt adds when that tool is offered.
FORM_GUIDANCE = (
    "When the person asks to run an installed Workflow, call " + FORM_TOOL + " with its "
    "name and only the run values they already stated; never ask for its run values or its "
    "settings in prose and never guess them: the form asks the person."
)
#: A run request is a short message; a long one is a task for the model.
MAX_INTENT_CHARS = 400

_RUN_VERB = (
    r"(?:執行|运行|運行|跑一下|跑一次|跑|啟動|启动|開始跑|开始跑|"
    r"\brun\b|\bstart\b|\blaunch\b|\bexecute\b|\btrigger\b)"
)
_RUN = re.compile(_RUN_VERB, re.IGNORECASE)
# A question about a Workflow, its results or a refusal to run it is not a
# request to run it now: the model answers those.
_NOT_A_RUN = re.compile(
    r"(怎麼|怎么|如何|為什麼|为什么|什麼是|什么是|是什麼|是什么|說明|说明|介紹|介绍|解釋|解释|"
    r"失敗|失败|錯誤|错误|結果|结果|紀錄|记录|日誌|日志|不要|別|别|取消|停止|"
    r"\bhow\b|\bwhy\b|\bwhat\b|\bexplain\b|\bfailed\b|\berror\b|\bresults?\b|\blogs?\b|"
    r"\bdon'?t\b|\bdo not\b|\bstop\b|\bcancel\b)",
    re.IGNORECASE,
)
_EDGE_BEFORE = r"(?<![A-Za-z0-9_./-])"
_EDGE_AFTER = r"(?![A-Za-z0-9_/-])"
_VALUE = r"(?:\"[^\"]*\"|'[^']*'|[^\s,，;；]+)"
_PAIR = re.compile(r"(?<![A-Za-z0-9_])([A-Za-z_][A-Za-z0-9_]*)\s*[=:：]\s*(" + _VALUE + ")")
_YES = {"yes", "y", "true", "1", "on", "是", "對", "对", "好", "要"}
_NO = {"no", "n", "false", "0", "off", "否", "不", "不要"}


@dataclass(frozen=True)
class RunIntent:
    """An explicit request to run one installed Workflow, with what was given."""

    manifest: WorkflowManifest
    prefill: dict[str, Any]


def _distinctive(name: str) -> bool:
    """A name nobody uses as an ordinary word: it may appear anywhere in a
    request. A plain word such as `push` must follow the run verb."""
    return bool(re.search(r"[-_/0-9]", name)) or len(name) >= 12


def _name_pattern(name: str) -> str:
    parts = [re.escape(part) for part in re.split(r"[-_\s]+", name) if part]
    return r"[-_\s]?".join(parts)


def _spans(text: str, manifest: WorkflowManifest) -> list[tuple[int, int]]:
    identity = manifest.metadata.identity
    found: list[tuple[int, int]] = []
    for name in (f"{identity.namespace}/{identity.name}", identity.name):
        body = _name_pattern(name)
        if not body:
            continue
        if _distinctive(name):
            pattern = _EDGE_BEFORE + "(" + body + ")" + _EDGE_AFTER
        else:
            # Only right after the verb: "run push", "執行 push workflow".
            pattern = (
                _RUN_VERB + r"\s*(?:the\s+)?(?:workflow\s+)?[「『\"']?(" + body + ")" + _EDGE_AFTER
            )
        for match in re.finditer(pattern, text, re.IGNORECASE):
            found.append(match.span(1))
    return found


def run_intent(text: str, manifests: Iterable[WorkflowManifest]) -> RunIntent | None:
    """The one installed Workflow `text` asks to run, or None.

    Needs a run verb and exactly one named Workflow (a name inside a longer
    matched name does not count: `release-package/commit` names `commit` only
    once). Questions, refusals and long task descriptions are left to the
    model. Never guesses between two Workflows.
    """
    message = text.strip()
    if not message or len(message) > MAX_INTENT_CHARS or message.startswith("/"):
        return None
    if not _RUN.search(message) or _NOT_A_RUN.search(message):
        return None
    matched: list[tuple[WorkflowManifest, tuple[int, int]]] = []
    for manifest in manifests:
        for span in _spans(message, manifest):
            matched.append((manifest, span))
    if not matched:
        return None
    # Drop a match lying inside another Workflow's longer match.
    kept = [
        (manifest, span)
        for manifest, span in matched
        if not any(
            other_span != span and other_span[0] <= span[0] and span[1] <= other_span[1]
            for other, other_span in matched
            if other is not manifest
        )
    ]
    chosen = {item.metadata.identity.key: item for item, _ in kept}
    if len(chosen) != 1:
        return None
    manifest = next(iter(chosen.values()))
    return RunIntent(manifest, prefill_from_text(manifest, message))


def _convert(field: WorkflowParameter, raw: str) -> Any:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        value = value[1:-1].strip()
    if field.kind == "boolean":
        lowered = value.casefold()
        return True if lowered in _YES else False if lowered in _NO else None
    if field.kind == "integer":
        return int(value) if re.fullmatch(r"-?\d+", value) else None
    if field.kind == "number":
        try:
            return float(value) if "." in value else int(value)
        except ValueError:
            return None
    if field.multiple or field.kind in ("text_list", "emails"):
        return [_choice(field, part.strip()) for part in re.split(r"[,|]", value) if part.strip()]
    if field.kind == "select":
        return _choice(field, value)
    return value


def _choice(field: WorkflowParameter, value: str) -> str:
    """A declared choice by value or label, else the text as given."""
    for choice in field.choices:
        if value.casefold() == (choice.label or "").casefold():
            return choice.value
    for declared in field.choice_values:
        if value.casefold() == declared.casefold():
            return declared
    return value


def prefill_from_text(manifest: WorkflowManifest, text: str) -> dict[str, Any]:
    """`name=value` / `name: value` pairs a person typed after the request.

    Field names match case-insensitively; anything that is not a valid value
    of a runtime field is dropped rather than refused (the form asks again).
    """
    fields = {item.name.casefold(): item for item in manifest.parameters}
    given: dict[str, Any] = {}
    for key, raw in _PAIR.findall(text):
        field = fields.get(key.casefold())
        if field is None:
            continue
        converted = _convert(field, raw)
        if converted is not None and converted != []:
            given[field.name] = converted
    return person_prefill(manifest, given)


def _kept(fields: Iterable[WorkflowParameter], values: Mapping[str, Any]) -> dict[str, Any]:
    kept: dict[str, Any] = {}
    for field in fields:
        if field.name not in values or field.kind == "upload":
            # An upload must be stored by the form; a path is never prefilled.
            continue
        value = values[field.name]
        if parameter_value_problem(field, value) is not None:
            continue
        try:
            reject_embedded_secrets({"value": value})
        except ValueError:
            continue
        kept[field.name] = value
    return kept


def person_prefill(
    manifest: WorkflowManifest,
    values: Mapping[str, Any],
    channels: tuple[ParameterChannel, ...] = ("web", "telegram"),
) -> dict[str, Any]:
    """Values a person gave: runtime fields shown on a person's form, valid."""
    seen: dict[str, WorkflowParameter] = {}
    for channel in channels:
        for field in ordered_fields(manifest, channel):
            seen.setdefault(field.name, field)
    return _kept(seen.values(), values)


def agent_prefill(manifest: WorkflowManifest, values: Mapping[str, Any]) -> dict[str, Any]:
    """Values a model gave: only fields it may set (agent channel, never a
    privileged `confirm` field), valid; everything else is the person's."""
    return _kept(agent_fields(manifest), values)


def missing_settings(manifest: WorkflowManifest, stored: Mapping[str, Any]) -> list[dict[str, str]]:
    """Required settings (`scope: static`) with neither a value nor a default."""
    return [
        {"name": field.name, "label": field.label}
        for field in static_fields(manifest)
        if field.required and stored.get(field.name) is None and field.default is None
    ]


def form_offer(
    manifest: WorkflowManifest,
    prefill: Mapping[str, Any],
    settings: Callable[[WorkflowManifest], Mapping[str, Any]] | None = None,
    *,
    origin: str = "rule",
) -> dict[str, Any]:
    """The hand-off the channels render. Settings that cannot be read count
    as not set, so the form points to the settings page rather than failing."""
    try:
        stored = dict(settings(manifest)) if settings is not None else {}
    except Exception:  # noqa: BLE001 - an unreadable store is "not set" here
        stored = {}
    identity = manifest.metadata.identity
    offer: dict[str, Any] = {
        "kind": OFFER_KEY,
        "workflow": identity.model_dump(mode="json"),
        "title": identity.name,
        "description": manifest.description,
        "prefill": dict(prefill),
        "missing_settings": missing_settings(manifest, stored),
        "origin": origin,
    }
    offer["message"] = offer_message(offer)
    return offer


def offer_message(offer: Mapping[str, Any]) -> str:
    """The chat text that goes with the form (kept in the conversation)."""
    title = str(offer.get("title") or "this Workflow")
    missing = offer.get("missing_settings") or []
    if missing:
        names = ", ".join(str(item.get("label") or item.get("name")) for item in missing)
        return (
            f"{title} cannot run yet: these settings are not set: {names}. Settings are "
            f"set once on the Workflow's settings page (Capabilities > Workflows > "
            f"{title} > Settings), not in the chat."
        )
    text = f"Run {title}: fill in the form below and press Run."
    if offer.get("prefill"):
        text += " The values you already gave are filled in; check them first."
    return text


def offer_in(tools: Iterable[Any]) -> dict[str, Any] | None:
    """The last `workflow_form` offer among a turn's tool executions."""
    found: dict[str, Any] | None = None
    for item in tools:
        host = getattr(item, "host", None)
        data = getattr(host, "data", None) if host is not None else None
        if isinstance(data, dict) and isinstance(data.get(OFFER_KEY), dict):
            found = data[OFFER_KEY]
    return found
