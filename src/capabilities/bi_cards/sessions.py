"""The two page-embedded AI design sessions of a BI dataset (BI ingest §9).

Session B (phase 5, `methods.py`) designs an ingest method; Session A (phase
6, `schema_session.py`) designs a schema draft. Both are built like the
Knowledge page's Skill assistant (`host_runtime/skill_assist.py`): one model
call per turn with structured output and no tools, checked by code with the
problems fed back (up to 3 attempts, as `workflow_author.conversation`), and
nothing changes until the person applies a suggestion.

Where turns are kept: the dataset's `staging.sqlite`, table `sessions` (one
row per session, its turns as JSON). That is the spec's place (§3.3, §9):
next to the runs and sources a turn refers to, written with the same
read-only refusal for a subscribed dataset, and never in `bi.sqlite`, so a
conversation can never change cards. A restart of Agent Web keeps every turn.

Source text is sent as data: each excerpt sits between `extract.DATA_FENCE`
and `extract.DATA_END` in a user message and never in the system message.
Every assistant turn records exactly what was sent (source names,
classification, characters per excerpt, the cap) and the model alias, so the
panel can show it.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from capabilities.bi_cards import readers
from capabilities.bi_cards.extract import DATA_END, DATA_FENCE
from capabilities.bi_cards.staging import Staging, parse_kind
from capabilities.bi_cards.store import BiStoreError, now
from common.execution import TraceIdentifiers
from models.contracts import ModelClient, ModelMessage, ModelRequest, ModelRequirements

KINDS = ("method", "schema")
#: Characters of source excerpts per turn (§9.1: capped, default 12000).
EXCERPT_CAP = 12_000
MAX_MESSAGE = 4000
MAX_GOAL = 1000
MAX_TURNS_SENT = 12
MAX_SOURCES = 5
MAX_ATTEMPTS = 3
UNAVAILABLE = "沒有可用的模型：到 Settings 設定 Knowledge 使用的模型後再試；不用 AI 也可以直接編輯"


@dataclass
class Asked:
    """The outcome of one turn's model call(s)."""

    answer: dict[str, Any] | None
    attempts: int
    problems: list[str] = field(default_factory=list)
    failure: str | None = None


def trace() -> TraceIdentifiers:
    """Trace ids start with a letter, as the model clients require."""
    return TraceIdentifiers(
        trace_id=f"bi-session-{uuid.uuid4().hex}",
        request_id=f"bi-session-{uuid.uuid4().hex}",
        span_id=f"bi-turn-{uuid.uuid4().hex[:16]}",
    )


def model_or_refuse(ai: Any) -> tuple[ModelClient, str]:
    """The Knowledge model and alias, or `model_unavailable` (nothing stored)."""
    chosen = ai.model() if ai is not None else None
    if chosen is None:
        raise BiStoreError("model_unavailable", UNAVAILABLE)
    return chosen[0], chosen[1]


def model_state(ai: Any) -> dict[str, Any]:
    chosen = ai.model() if ai is not None else None
    if chosen is None:
        return {"available": False, "model": None, "message": UNAVAILABLE}
    return {"available": True, "model": chosen[1], "message": ""}


# -- storage -----------------------------------------------------------------


def create(staging: Staging, *, kind: str, target_ref: str, actor: str) -> dict[str, Any]:
    if kind not in KINDS:
        raise BiStoreError("session_kind_invalid", "kind 只能是 method 或 schema")
    staging.store.refuse_write()
    return staging.create_session(kind=kind, target_ref=target_ref, actor=actor)


def load(staging: Staging, session_id: str, kind: str | None = None) -> dict[str, Any]:
    found = staging.session(str(session_id))
    if found is None or (kind is not None and found["kind"] != kind):
        raise BiStoreError("session_unknown", "找不到這段對話")
    return found


def assistant_turn(
    staging: Staging, session: dict[str, Any], index: Any
) -> tuple[dict[str, Any], int]:
    turns = session["turns"]
    if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(turns):
        raise BiStoreError("turn_unknown", "找不到這一輪的建議")
    found = turns[index]
    if found.get("role") != "assistant" or not found.get("suggestion"):
        raise BiStoreError("turn_unknown", "這一輪沒有可以套用的建議")
    if found.get("applied"):
        raise BiStoreError("suggestion_applied", "這個建議已經套用過了")
    return found, index


def mark_applied(staging: Staging, session: dict[str, Any], index: int, applied: Any) -> None:
    session["turns"][index]["applied"] = applied
    staging.put_session(session)


# -- what is sent --------------------------------------------------------------


def _source_text(staging: Staging, source: dict[str, Any]) -> str:
    data = staging.source_bytes(source["id"])
    if parse_kind(source["name"]) == "text" or readers.suffix(source["name"]) in (".csv", ".tsv"):
        return data.decode("utf-8-sig", errors="replace")
    if readers.readable(source["name"]):
        # A workbook goes as its tables, one row per line.
        lines = []
        for table in readers.read_tables(source["name"], data):
            lines.append(f"## {table['title']}")
            lines.append(" | ".join(str(c) for c in table["columns"]))
            for row in table["rows"]:
                lines.append(" | ".join(str(v) for v in row["cells"].values()))
        return "\n".join(lines)
    raise BiStoreError("source_unsupported", f"「{source['name']}」無法讀成文字，不能當作樣本")


def excerpts(
    staging: Staging, source_ids: Any, cap: int = EXCERPT_CAP
) -> tuple[str, list[dict[str, Any]]]:
    """(the fenced sample text, what was sent per source). The cap is shared
    equally by the chosen sources."""
    if source_ids in (None, []):
        return "", []
    if not isinstance(source_ids, list) or not all(isinstance(s, str) for s in source_ids):
        raise BiStoreError("source_ids_invalid", "source_ids 必須是來源 id 清單")
    chosen = list(dict.fromkeys(source_ids))[:MAX_SOURCES]
    share = cap // len(chosen)
    blocks, sent = [], []
    for source_id in chosen:
        source = staging.source(source_id)
        if source is None:
            raise BiStoreError("source_unknown", "找不到這個來源")
        text = _source_text(staging, source)
        piece = text[:share]
        sent.append(
            {
                "id": source["id"],
                "name": source["name"],
                "classification": source["classification"],
                "chars": len(piece),
                "of": len(text),
                "truncated": len(piece) < len(text),
            }
        )
        blocks.append(
            f"Sample source 「{source['name']}」 (first {len(piece)} of {len(text)} characters)\n"
            f"{DATA_FENCE}\n{piece}\n{DATA_END}"
        )
    return "\n\n".join(blocks), sent


def fenced(label: str, text: str) -> str:
    """Text derived from sources (e.g. trial candidates) also travels as data."""
    return f"{label}\n{DATA_FENCE}\n{text}\n{DATA_END}"


# -- one turn ------------------------------------------------------------------


def history(turns: Sequence[dict[str, Any]]) -> list[ModelMessage]:
    """Earlier turns as chat messages: the person's words, and the model's
    earlier suggestions as the JSON it gave."""
    found = []
    for turn in list(turns)[-MAX_TURNS_SENT:]:
        if turn.get("role") == "user":
            found.append(ModelMessage(role="user", text=str(turn.get("text") or "")[:MAX_MESSAGE]))
        elif turn.get("suggestion"):
            shown = {k: v for k, v in turn["suggestion"].items() if k != "result"}
            text = json.dumps(shown, ensure_ascii=False)[:MAX_MESSAGE]
            found.append(ModelMessage(role="assistant", text=text))
    return found


def ask(
    model: ModelClient,
    alias: str,
    *,
    system: str,
    context: str,
    turns: Sequence[dict[str, Any]],
    contract: str,
    check: Callable[[dict[str, Any]], list[str]],
    max_attempts: int = MAX_ATTEMPTS,
) -> Asked:
    """One turn: structured output, no tools; an answer `check` finds
    problems with is asked again with the problems, up to `max_attempts`."""
    problems: list[str] = []
    last: dict[str, Any] | None = None
    for attempt in range(1, max_attempts + 1):
        messages = [
            ModelMessage(role="system", text=system),
            ModelMessage(role="user", text=context),
            ModelMessage(role="assistant", text="I have read the context and the data."),
            *history(turns),
        ]
        if problems:
            messages.append(
                ModelMessage(
                    role="user",
                    text="Your last answer could not be used: "
                    + "; ".join(problems)
                    + ". Answer again with the JSON object only.",
                )
            )
        response = model.generate(
            ModelRequest(
                trace=trace(),
                model_alias=alias,
                messages=tuple(messages),
                requirements=ModelRequirements(structured_output=True),
                output_contract=contract,
                max_output_tokens=6000,
            )
        )
        if response.failure is not None:
            return Asked(None, attempt, [], f"model_unavailable: {response.failure.code}")
        answer = response.structured_output
        if not isinstance(answer, dict):
            answer = _salvage(response.text)
        if not isinstance(answer, dict):
            problems = ["the answer was not a JSON object"]
            continue
        last = answer
        problems = check(answer)
        if not problems:
            return Asked(answer, attempt)
    return Asked(last, max_attempts, problems, None)


def _salvage(text: str) -> Any:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except ValueError:
        return None


def strings(value: Any, limit: int = 20) -> list[str]:
    """A list of short texts from the answer (anything else becomes [])."""
    if not isinstance(value, list):
        return []
    return [str(v).strip()[:500] for v in value if str(v).strip()][:limit]


def record(
    staging: Staging,
    session: dict[str, Any],
    *,
    message: str,
    actor: str,
    alias: str,
    asked: Asked,
    sent: dict[str, Any],
    suggestion: dict[str, Any] | None,
) -> dict[str, Any]:
    """Keep the person's turn and the model's answer (or why there is none)."""
    session["turns"].append({"role": "user", "text": message, "at": now(), "by": actor})
    error = None
    if asked.failure is not None:
        error = {"code": "model_unavailable", "message": f"模型沒有回應（{asked.failure}）"}
    elif suggestion is None:
        error = {
            "code": "model_output_invalid",
            "message": f"模型的回答 {asked.attempts} 次都不符合格式：" + "; ".join(asked.problems),
        }
    session["turns"].append(
        {
            "role": "assistant",
            "at": now(),
            "model": alias,
            "attempts": asked.attempts,
            "problems": asked.problems,
            "sent": sent,
            "suggestion": suggestion,
            "error": error,
            "applied": None,
        }
    )
    session["model"] = alias
    staging.put_session(session)
    return session


def check_message(message: Any) -> str:
    text = str(message or "").strip()
    if not text:
        raise BiStoreError("message_missing", "請寫下你想要的調整")
    if len(text) > MAX_MESSAGE:
        raise BiStoreError("message_too_long", f"訊息最多 {MAX_MESSAGE} 個字")
    return text
