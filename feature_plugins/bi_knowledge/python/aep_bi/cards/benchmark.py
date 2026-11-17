"""A short domain benchmark for BI extraction (BI ingest phase 7).

`docs/phases/BI_INGEST.md` §11 item 10: a few fictional notes, each with an
expected file (`aep.bi.benchmark.expected/v1`), scored on the candidates a run
produced (the candidate shape of `docs/CONTRACTS.md` "BI ingest runs" and "BI
AI path: extraction runs"). The scorer is a pure function: no model call, no
store, no file write. It checks five things the owner asked for:

- **fact**: a field the note states must be `basis: "fact"` and its evidence
  excerpt must overlap the expected substring (and, given the note's text,
  its locator must cover a line holding that substring);
- **inference**: a field the note only implies must be `basis: "inference"`;
- **unknown**: a field the note does not support must be absent or
  `basis: "unknown"`, never claimed;
- **duplicate**: two spellings of one entity must end as one candidate, or be
  flagged `match: "ambiguous"` for the person to decide;
- **missing**: an item that must not be produced (an Opportunity with no
  stated need, a distributor as a Competitor) must not be committable: it is
  absent or rejected by default.

Expected candidates are also counted (found / expected). The score is the
share of passed checks; every failed check is listed in plain words.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aep_bi.cards.schema import norm_key

EXPECTED_FORMAT = "aep.bi.benchmark.expected/v1"
CATEGORIES = ("candidates", "fact", "inference", "unknown", "duplicate", "missing")
BASES = ("fact", "inference", "unknown")


@dataclass(frozen=True)
class Case:
    """One benchmark note: its file name, text and expected answer."""

    note: str
    text: str
    expected: dict[str, Any]


def load_cases(folder: Path) -> list[Case]:
    """Every `<note>.md` with its `<note>.expected.json` in `folder`, by name."""
    cases = []
    for path in sorted(folder.glob("*.expected.json")):
        expected = json.loads(path.read_text(encoding="utf-8"))
        note = folder / str(expected.get("note") or "")
        cases.append(Case(note.name, note.read_text(encoding="utf-8"), expected))
    return cases


def check_expected(expected: dict[str, Any], text: str) -> list[str]:
    """Problems of an expected file itself (shape, and fact evidence that is
    not in the note); empty when it can be scored."""
    problems = []
    if expected.get("format") != EXPECTED_FORMAT:
        problems.append(f"format must be {EXPECTED_FORMAT}")
    for item in expected.get("candidates") or []:
        label = f"{item.get('entity_type')} {item.get('name')}"
        for name, spec in (item.get("fields") or {}).items():
            basis = spec.get("basis")
            if basis not in BASES:
                problems.append(f"{label}.{name}: basis must be one of {', '.join(BASES)}")
            elif basis == "fact" and _squeeze(spec.get("evidence")) not in _squeeze(text):
                problems.append(
                    f"{label}.{name}: evidence {spec.get('evidence')!r} is not in the note"
                )
    for group in expected.get("duplicates") or []:
        if len(group.get("names") or []) < 2:
            problems.append(f"duplicate group of {group.get('entity_type')} needs two names")
    return problems


# -- matching ------------------------------------------------------------------


def _squeeze(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip().lower()


def _name(candidate: dict[str, Any]) -> str:
    return str(candidate.get("name") or candidate.get("canonical_key") or "")


def _names(item: dict[str, Any]) -> list[str]:
    found = [item.get("name"), *(item.get("aliases") or []), *(item.get("names") or [])]
    return [norm_key(n) for n in found if n]


def _named(candidate: dict[str, Any], wanted: Sequence[str], *, loose: bool) -> bool:
    mine = norm_key(_name(candidate))
    if not mine:
        return False
    if mine in wanted:
        return True
    return loose and any(w and (w in mine or mine in w) for w in wanted)


def _of_type(candidates: Iterable[dict[str, Any]], entity_type: str) -> list[dict[str, Any]]:
    return [c for c in candidates if c.get("entity_type") == entity_type]


def _fields(candidate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(f.get("field")): f for f in candidate.get("fields") or []}


def _lines_with(text: str, wanted: str) -> set[int]:
    """1-based numbers of the lines holding `wanted` (whitespace ignored)."""
    target = _squeeze(wanted)
    return {n for n, line in enumerate(text.split("\n"), start=1) if target in _squeeze(line)}


def _value_matches(value: Any, wanted: Any) -> bool:
    have = value if isinstance(value, list) else [value]
    need = wanted if isinstance(wanted, list) else [wanted]
    keys = {norm_key(v) for v in have if v is not None}
    return all(norm_key(w) in keys for w in need)


# -- one field -------------------------------------------------------------------


def _field_failure(
    spec: dict[str, Any],
    got: dict[str, Any] | None,
    candidate: dict[str, Any],
    text: str | None,
) -> tuple[str, str] | None:
    """(code, message) when the field does not meet `spec`, else None."""
    want = spec["basis"]
    basis = None if got is None else str(got.get("basis") or "unknown")
    if want == "unknown":
        if basis in (None, "unknown"):
            return None
        return "wrong_basis", f"原文沒有依據，卻標成「{basis}」（值：{got and got.get('value')}）"
    if got is None:
        return "field_missing", f"應有這個欄位（{want}），但沒有產生"
    if want == "inference":
        if basis != "inference":
            return "wrong_basis", f"應標成推論，卻是「{basis}」"
    elif basis == "fact":
        excerpts = [str(e.get("excerpt") or "") for e in got.get("evidence") or []]
        wanted = _squeeze(spec.get("evidence"))
        overlapping = [
            e
            for e in got.get("evidence") or []
            if _squeeze(e.get("excerpt"))
            and (wanted in _squeeze(e.get("excerpt")) or _squeeze(e.get("excerpt")) in wanted)
        ]
        if not excerpts:
            return "evidence_missing", "標成事實但沒有出處"
        if not overlapping:
            return (
                "evidence_mismatch",
                f"出處「{'／'.join(excerpts)}」不是「{spec.get('evidence')}」",
            )
        if text is not None:
            lines = _lines_with(text, str(spec.get("evidence")))
            placed = [
                e
                for e in overlapping
                if "line_start" not in (e.get("locator") or {})
                or any(
                    int(e["locator"]["line_start"]) <= n <= int(e["locator"]["line_end"])
                    for n in lines
                )
            ]
            if not placed:
                return "evidence_mismatch", "出處的行號沒有指到原文中的那一句"
    else:
        codes = [w.get("code") for w in candidate.get("warnings") or []]
        if basis == "unknown" and "evidence_not_found" in codes:
            return "evidence_missing", "模型引用的原文不在來源中（evidence_not_found），沒有出處"
        return "wrong_basis", f"應是有出處的事實，卻是「{basis}」"
    if "value" in spec and not _value_matches(got.get("value"), spec["value"]):
        return "wrong_value", f"值應包含「{spec['value']}」，卻是「{got.get('value')}」"
    return None


# -- one note ---------------------------------------------------------------------


def _pick(
    item: dict[str, Any], pool: list[dict[str, Any]], text: str | None
) -> dict[str, Any] | None:
    mine = _of_type(pool, str(item.get("entity_type")))
    if item.get("name"):
        wanted = _names(item)
        for loose in (False, True):
            found = [c for c in mine if _named(c, wanted, loose=loose)]
            if found:
                return found[0]
        return None
    if not mine:
        return None

    def passed(candidate: dict[str, Any]) -> int:
        got = _fields(candidate)
        return sum(
            _field_failure(spec, got.get(name), candidate, text) is None
            for name, spec in (item.get("fields") or {}).items()
        )

    return max(mine, key=passed)


def score(
    candidates: Sequence[dict[str, Any]],
    expected: dict[str, Any],
    *,
    text: str | None = None,
) -> dict[str, Any]:
    """Score one run's candidates against one expected file. `text` (the
    note) lets the scorer also check evidence line numbers."""
    note = str(expected.get("note") or "")
    tally = {c: {"ok": 0, "expected": 0} for c in CATEGORIES}
    failures: list[dict[str, Any]] = []

    def fail(category: str, code: str, item: dict[str, Any], message: str, **extra: Any) -> None:
        failures.append(
            {
                "note": note,
                "category": category,
                "code": code,
                "entity_type": item.get("entity_type"),
                "name": item.get("name") or "、".join(item.get("names") or []) or None,
                "field": extra.get("field"),
                "message": message,
            }
        )

    pool = list(candidates)
    claimed: list[dict[str, Any]] = []
    for item in expected.get("candidates") or []:
        tally["candidates"]["expected"] += 1
        found = _pick(item, pool, text)
        if found is None:
            specs = item.get("fields") or {}
            for spec in specs.values():
                tally[spec["basis"]]["expected"] += 1
            fail(
                "candidates", "candidate_missing", item, f"沒有產生（{len(specs)} 個欄位無法檢查）"
            )
            continue
        pool.remove(found)
        claimed.append(found)
        tally["candidates"]["ok"] += 1
        got = _fields(found)
        for name, spec in (item.get("fields") or {}).items():
            category = spec["basis"]
            tally[category]["expected"] += 1
            problem = _field_failure(spec, got.get(name), found, text)
            if problem is None:
                tally[category]["ok"] += 1
            else:
                fail(category, problem[0], {**item, "name": _name(found)}, problem[1], field=name)

    for group in expected.get("duplicates") or []:
        tally["duplicate"]["expected"] += 1
        wanted = _names(group)
        mine = [
            c
            for c in _of_type(candidates, str(group.get("entity_type")))
            if _named(c, wanted, loose=False)
        ]
        same_card = {tuple(c.get("match_ids") or ()) for c in mine}
        flagged = any(c.get("match") == "ambiguous" for c in mine)
        existing = all(c.get("match") == "existing" for c in mine) and len(same_card) == 1
        if len(mine) == 1 or (len(mine) > 1 and (flagged or existing)):
            tally["duplicate"]["ok"] += 1
        elif not mine:
            fail("duplicate", "duplicate_absent", group, "兩種寫法都沒有產生候選卡")
        else:
            shown = "、".join(_name(c) for c in mine)
            fail(
                "duplicate",
                "duplicate_not_merged",
                group,
                f"同一個實體成了 {len(mine)} 張：{shown}",
            )

    produced_rejected: list[str] = []
    for item in expected.get("forbidden") or []:
        tally["missing"]["expected"] += 1
        wanted = _names(item)
        mine = [
            c
            for c in _of_type(candidates, str(item.get("entity_type")))
            if not wanted or _named(c, wanted, loose=True)
        ]
        open_ = [c for c in mine if c.get("review") != "rejected"]
        produced_rejected.extend(_name(c) for c in mine if c.get("review") == "rejected")
        if open_:
            shown = "、".join(_name(c) for c in open_)
            fail("missing", "forbidden_produced", item, f"不應產生卻產生了（可寫入）：{shown}")
        else:
            tally["missing"]["ok"] += 1

    extra = [
        f"{c.get('entity_type')} {_name(c)}"
        for c in candidates
        if c not in claimed and _name(c) not in produced_rejected
    ]
    return _result(note, tally, failures, extra=extra, rejected=produced_rejected)


def _result(
    note: str,
    tally: dict[str, dict[str, int]],
    failures: list[dict[str, Any]],
    **more: Any,
) -> dict[str, Any]:
    checks = sum(t["expected"] for t in tally.values())
    passed = sum(t["ok"] for t in tally.values())
    codes = [f["code"] for f in failures]
    return {
        "note": note,
        "categories": tally,
        "counts": {
            "found": tally["candidates"]["ok"],
            "expected": tally["candidates"]["expected"],
            "wrong_basis": codes.count("wrong_basis"),
            "evidence_not_matching": codes.count("evidence_missing")
            + codes.count("evidence_mismatch"),
            "forbidden_produced": codes.count("forbidden_produced"),
            "duplicates_not_merged": codes.count("duplicate_not_merged"),
        },
        "score": round(100.0 * passed / checks, 1) if checks else 100.0,
        "passed": passed,
        "checks": checks,
        "failures": failures,
        **more,
    }


def summarize(results: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """Every note's result added up, with the notes kept."""
    tally = {c: {"ok": 0, "expected": 0} for c in CATEGORIES}
    failures: list[dict[str, Any]] = []
    for result in results:
        for category, counts in result["categories"].items():
            tally[category]["ok"] += counts["ok"]
            tally[category]["expected"] += counts["expected"]
        failures.extend(result["failures"])
    return _result("(all)", tally, failures, notes=list(results))


# -- the report ---------------------------------------------------------------------

_CATEGORY_LABEL = {
    "candidates": "候選卡（找到／應有）",
    "fact": "事實（有出處）",
    "inference": "推論",
    "unknown": "無依據（不應宣稱）",
    "duplicate": "重複名稱（合併或標成名稱相近）",
    "missing": "不應產生的項目",
}


def render_markdown(summary: dict[str, Any], *, title: str, preface: Sequence[str] = ()) -> str:
    """A plain report: the overall score, a table per category, per-note
    scores and every failure in words."""
    lines = [f"# {title}", "", *preface]
    if preface:
        lines.append("")
    lines += [
        f"**總分：{summary['score']}%**（{summary['passed']}／{summary['checks']} 項檢查通過）",
        "",
        "| 類別 | 通過 | 應有 |",
        "|---|---|---|",
    ]
    for category in CATEGORIES:
        counts = summary["categories"][category]
        lines.append(f"| {_CATEGORY_LABEL[category]} | {counts['ok']} | {counts['expected']} |")
    c = summary["counts"]
    lines += [
        "",
        f"- 找到的候選卡：{c['found']}／{c['expected']}",
        f"- 依據標錯：{c['wrong_basis']}",
        f"- 出處不符或沒有出處：{c['evidence_not_matching']}",
        f"- 不應產生卻產生：{c['forbidden_produced']}",
        f"- 重複名稱沒有合併：{c['duplicates_not_merged']}",
        "",
        "## 各篇",
        "",
        "| 筆記 | 分數 | 通過／檢查 |",
        "|---|---|---|",
    ]
    for result in summary.get("notes") or []:
        lines.append(
            f"| {result['note']} | {result['score']}% | {result['passed']}／{result['checks']} |"
        )
    lines += ["", "## 沒有通過的檢查", ""]
    if not summary["failures"]:
        lines.append("全部通過。")
    for f in summary["failures"]:
        where = f"{f['entity_type']}「{f['name'] or '（任一）'}」" + (
            f".{f['field']}" if f.get("field") else ""
        )
        lines.append(f"- {f['note']}・{_CATEGORY_LABEL[f['category']]}・{where}：{f['message']}")
    extras = [(r["note"], x) for r in summary.get("notes") or [] for x in r.get("extra") or []]
    if extras:
        lines += ["", "## 額外的候選卡（不扣分，供人工檢查）", ""]
        lines += [f"- {note}：{item}" for note, item in extras]
    return "\n".join(lines) + "\n"
