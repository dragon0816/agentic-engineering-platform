"""The 「委派紀錄」 under an answer (multi-agent V1, `docs/CONTRACTS.md`
"Multi-agent delegation (V1)" → "Delegation record and live lines").

Built from the `agent__delegate` tool executions of one turn: each sub-agent
that ran, with its profile, status, a short summary, its artifacts and its
tokens. A refused delegation started no sub-agent and is left out. Agent Web
keeps the records on the answer (`ConversationMessage.delegations`) and draws
them as a collapsible block; Telegram adds them as summary lines to the reply.

It reads the tool's host data as plain JSON (never importing the core
delegation module), so it stays a view: a record it cannot read is skipped.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

#: The Host tool's name (`agent.delegation_scope.DELEGATE_TOOL`).
DELEGATE_TOOL = "agent__delegate"
#: A refusal starts no sub-run (the contract's "Refusal codes").
REFUSAL_CODES = frozenset(
    {
        "delegation_disabled",
        "delegation_depth_exceeded",
        "delegation_limit_reached",
        "delegation_arguments_invalid",
        "delegation_target_not_allowed",
        "delegation_target_unavailable",
        "delegation_profile_ambiguous",
        "delegation_artifact_unknown",
        "delegation_time_exhausted",
    }
)
#: At most three run per turn; the cap only bounds a malformed result.
MAX_RECORDS = 6
MAX_SUMMARY_CHARS = 280
MAX_ARTIFACTS = 10
STATUS_LABELS = {
    "succeeded": "完成",
    "needs_input": "需要資訊",
    "awaiting_approval": "等待確認",
    "failed": "失敗",
}

#: The Host path of a file artifact id in this session, or None.
FileResolver = Callable[[str], str | None]


def _short(text: object, limit: int = MAX_SUMMARY_CHARS) -> str:
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rstrip() + "…"


def _count(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _record(delegation: dict[str, Any], resolve: FileResolver | None) -> dict[str, Any] | None:
    status = delegation.get("status")
    if status not in STATUS_LABELS:
        return None
    failure = delegation.get("failure")
    code = failure.get("code") if isinstance(failure, dict) else None
    if code in REFUSAL_CODES:
        return None
    artifacts: list[dict[str, Any]] = []
    for item in delegation.get("artifacts") or ():
        if not isinstance(item, dict) or item.get("kind") not in ("run", "file"):
            continue
        shown: dict[str, Any] = {
            "kind": item["kind"],
            "id": _short(item.get("id"), 80),
            "name": _short(item.get("name"), 120),
        }
        if isinstance(item.get("status"), str):
            shown["status"] = _short(item["status"], 40)
        if item["kind"] == "file" and resolve is not None:
            path = resolve(str(item.get("id") or ""))
            if path:
                shown["path"] = path
        artifacts.append(shown)
        if len(artifacts) >= MAX_ARTIFACTS:
            break
    raw_tokens = delegation.get("tokens")
    tokens: dict[str, Any] = raw_tokens if isinstance(raw_tokens, dict) else {}
    record: dict[str, Any] = {
        "profile": _short(delegation.get("profile"), 200),
        "status": status,
        "summary": _short(delegation.get("summary")),
        "validated": delegation.get("validated") is True,
        "artifacts": artifacts,
        "tokens": {
            "input": _count(tokens.get("input")),
            "output": _count(tokens.get("output")),
            "model_calls": _count(tokens.get("model_calls")) or 0,
        },
        "tool_calls": len(delegation.get("tool_calls") or ()),
        "elapsed_s": float(delegation.get("elapsed_s") or 0.0),
    }
    if code:
        record["failure_code"] = _short(code, 80)
    if isinstance(delegation.get("question"), str):
        record["question"] = _short(delegation["question"])
    if isinstance(delegation.get("host_note"), str) and delegation["host_note"]:
        record["host_note"] = _short(delegation["host_note"])
    return record


def records_from(tools: Iterable[Any], resolve: FileResolver | None = None) -> list[dict[str, Any]]:
    """The 委派紀錄 of one turn from its tool executions, in call order."""
    records: list[dict[str, Any]] = []
    for item in tools:
        host = getattr(item, "host", None)
        data = getattr(host, "data", None)
        if getattr(item, "name", None) != DELEGATE_TOOL or not isinstance(data, dict):
            continue
        delegation = data.get("delegation")
        if not isinstance(delegation, dict):
            continue
        record = _record(delegation, resolve)
        if record is not None:
            records.append(record)
        if len(records) >= MAX_RECORDS:
            break
    return records


def _tokens_text(tokens: dict[str, Any]) -> str:
    calls = tokens.get("model_calls") or 0
    if tokens.get("input") is None and tokens.get("output") is None:
        return f"{calls} 次模型呼叫"
    return f"tokens {tokens.get('input') or 0:,}/{tokens.get('output') or 0:,}（{calls} 次呼叫）"


def text_lines(records: Iterable[dict[str, Any]]) -> list[str]:
    """The 委派紀錄 as chat text (Telegram's reply): a heading and, per
    sub-agent, its status line, summary and artifacts."""
    shown = list(records)
    if not shown:
        return []
    lines = ["委派紀錄"]
    for record in shown:
        label = STATUS_LABELS.get(str(record.get("status")), str(record.get("status")))
        head = f"• {record.get('profile', '')} — {label}"
        if record.get("failure_code") and record.get("status") == "failed":
            head += f"（{record['failure_code']}）"
        head += f" · {float(record.get('elapsed_s') or 0):.1f} s · "
        head += _tokens_text(record.get("tokens") or {})
        lines.append(head)
        if record.get("question"):
            lines.append(f"  需要：{record['question']}")
        elif record.get("summary"):
            lines.append(f"  {record['summary']}")
        if record.get("host_note"):
            lines.append(f"  Host 註記：{record['host_note']}")
        artifacts = record.get("artifacts") or []
        if artifacts:
            names = [
                f"{item['id']} {item['name']}"
                + (f"（{item['status']}）" if item.get("status") else "")
                for item in artifacts
            ]
            lines.append("  產出：" + "、".join(names))
    return lines


def files(records: Iterable[dict[str, Any]]) -> list[str]:
    """The Host paths of the records' file artifacts that resolved."""
    return [
        str(item["path"])
        for record in records
        for item in record.get("artifacts") or ()
        if item.get("kind") == "file" and item.get("path")
    ]
