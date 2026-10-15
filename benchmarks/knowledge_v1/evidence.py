"""What a reply shows about the Knowledge harness, and whether its citations are real.

A question reaches Knowledge by one of two routes, both through Agent Web chat:

- direct: the host's Knowledge harness answered (`answer.harness`, and the
  answer record in `answer.outcome.capability.data`);
- tool: the conversation model called a `knowledge__*` tool, whose
  capability result carries the same answer record.

A reply where neither happened did not use Knowledge at all. Citations are
checked against the Vault on disk: the cited file exists and the quoted
passage text is in it.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

# The Knowledge handler refuses with these codes when the Vault cannot answer.
INSUFFICIENT = {"knowledge_insufficient_evidence", "knowledge_not_grounded"}
_BRACKET = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")


def _answer(exchange: dict[str, Any]) -> dict[str, Any]:
    return ((exchange.get("reply") or {}).get("answer") or {}) if isinstance(exchange, dict) else {}


def knowledge_use(exchange: dict[str, Any]) -> dict[str, Any]:
    """Route, status and answer record of the Knowledge work in one turn."""
    answer = _answer(exchange)
    outcome = answer.get("outcome") or {}
    capability = outcome.get("capability") or {}
    harness = answer.get("harness")
    if harness or capability:
        failure = capability.get("failure") or {}
        phase = (harness or {}).get("phase") if isinstance(harness, dict) else None
        return {
            "route": "direct",
            "status": capability.get("status"),
            "failure": failure.get("code"),
            "phase": phase,
            "record": capability.get("data") or {},
            "text": str(answer.get("answer") or ""),
            "evidence": answer.get("evidence") or {},
            "tools": [],
        }
    conversation = outcome.get("conversation") or {}
    tools = conversation.get("tools") or []
    used = [t for t in tools if str(t.get("name", "")).startswith("knowledge__")]
    names = [str(t.get("name")) for t in tools]
    text = str(conversation.get("text") or answer.get("answer") or "")
    if not used:
        return {
            "route": "none",
            "status": conversation.get("status"),
            "failure": (conversation.get("failure") or {}).get("code"),
            "phase": None,
            "record": {},
            "text": text,
            "evidence": {},
            "tools": names,
        }
    harnessed = [
        t
        for t in used
        if isinstance((t.get("host") or {}).get("data"), dict)
        and "knowledge_harness" in t["host"]["data"]
    ]
    if harnessed:
        # Since 2026-10-09 the tool route runs the Knowledge Harness on the
        # host; a validated answer is the turn's answer, cited like the direct
        # route's.
        host = harnessed[-1]["host"]
        data = host["data"]
        return {
            "route": "tool",
            "status": host.get("status"),
            "failure": data.get("failure_code") or (host.get("failure") or {}).get("code"),
            "phase": data.get("phase") or conversation.get("status"),
            "record": data.get("record") or {},
            "text": text,
            "evidence": data.get("evidence") or {},
            "tools": names,
            "harnessed": True,
            "conversation_status": conversation.get("status"),
        }
    # The last Knowledge call is what the answer rests on; earlier ones were searches.
    good = [t for t in used if (t.get("capability") or {}).get("status") == "succeeded"]
    last = (good or used)[-1]
    capability = last.get("capability") or {}
    failure = capability.get("failure") or last.get("failure") or {}
    records = [(t.get("capability") or {}).get("data") or {} for t in good]
    return {
        "route": "tool",
        "status": capability.get("status"),
        "failure": failure.get("code"),
        "phase": conversation.get("status"),
        "record": capability.get("data") or {},
        "records": records,
        "text": text,
        "evidence": {},
        "tools": names,
        "conversation_status": conversation.get("status"),
    }


def cited_numbers(text: str) -> list[int]:
    """Passage numbers the text cites, `[2]`, `[1, 3]` and `[1-3]` alike, in order."""
    found: list[int] = []
    for group in _BRACKET.findall(text):
        for part in group.split(","):
            low, _, high = part.strip().partition("-")
            numbers = range(int(low), int(high) + 1) if high.strip() else [int(low)]
            found += [n for n in numbers if n not in found]
    return found


def _ref(passage: dict[str, Any]) -> str:
    citation = passage.get("citation") or {}
    return str(citation.get("wiki_page") or citation.get("raw_ref") or "")


def cited_passages(use: dict[str, Any]) -> list[dict[str, Any]]:
    """The passages the final answer rests on.

    Direct route: the `[n]` numbers in the answer index the record's passages
    from 1. Tool route: the conversation model writes its own answer and
    names sources by file path, so every passage from any Knowledge call in
    the turn whose file the answer names is taken; failing that, the passages
    the Knowledge answers themselves cited."""
    text = use.get("text") or ""
    if use.get("route") == "direct" or use.get("harnessed"):
        passages = ((use.get("record") or {}).get("answer") or {}).get("passages") or []
        return [
            {"number": n, **passages[n - 1]} for n in cited_numbers(text) if 1 <= n <= len(passages)
        ]
    pool: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in use.get("records") or [use.get("record") or {}]:
        for passage in (record.get("answer") or {}).get("passages") or []:
            key = _ref(passage) + "#" + str((passage.get("citation") or {}).get("section"))
            if key not in seen:
                seen.add(key)
                pool.append(passage)
    named = [p for p in pool if _ref(p) and (_ref(p) in text or Path(_ref(p)).stem in text)]
    if not named:
        for record in use.get("records") or [use.get("record") or {}]:
            named += [p for p in record.get("cited_passages") or [] if p not in named]
    return [{"number": i, **p} for i, p in enumerate(named, 1)]


def _flat(text: str) -> str:
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"\[\[([^\]|]*)(?:\|[^\]]*)?\]\]", r"\1", text)  # [[wiki link|label]]
    return re.sub(r"[\s`*_>#|]+", "", text).lower()


def verify(passage: dict[str, Any], vault: Path) -> dict[str, Any]:
    """Does the cited file exist in the Vault, and is the passage text in it?
    A passage starts with a "Title › Section" heading line the Vault does not
    hold verbatim, so that line is left out of the comparison."""
    citation = passage.get("citation") or {}
    ref = citation.get("wiki_page") if citation.get("kind") == "wiki" else citation.get("raw_ref")
    result: dict[str, Any] = {
        "number": passage.get("number"),
        "kind": citation.get("kind"),
        "ref": ref,
    }
    if not ref:
        return {**result, "ok": False, "why": "no file named"}
    path = (vault / ref).resolve()
    if vault.resolve() not in path.parents or not path.is_file():
        return {**result, "ok": False, "why": "file not in the Vault"}
    body = str(passage.get("text") or "")
    lines = body.splitlines()
    if len(lines) > 1 and "›" in lines[0]:
        body = "\n".join(lines[1:])
    file_text = _flat(path.read_text(encoding="utf-8", errors="replace"))
    # Compare in chunks: a passage may be trimmed or redacted at its ends.
    flat = _flat(body)
    chunks = [flat[i : i + 40] for i in range(0, max(len(flat) - 39, 1), 40)] or [flat]
    found = sum(1 for chunk in chunks if chunk and chunk in file_text)
    share = found / len(chunks) if chunks else 0.0
    return {
        **result,
        "ok": share >= 0.8,
        "text_found": round(share, 2),
        "why": "" if share >= 0.8 else "passage text not found in the file",
    }
