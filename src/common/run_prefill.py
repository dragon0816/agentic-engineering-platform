"""Run values a person stated in plain words, read from a "run X" request.

Owner finding 2026-10-25: 「幫我執行 43W SDE weekly report」 opened the
question flow and asked for the report week the message already named. This
module reads the obvious values deterministically, from the Workflow's own
declaration (field kinds, labels, examples, choices), and only when the
reading is unambiguous: a report week in the format the field's example
shows, an explicit date for the one date field, a declared choice named in
the text, or a dry-run phrase for a dry-run switch. Anything doubtful is
left out, so the form or question flow asks it as before. Callers validate
what comes back with the same field rules as a typed answer
(`workflow_run_form.person_prefill`).
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date
from typing import Any

from common.assets import WorkflowManifest, WorkflowParameter

# A week the person wrote: 2026_43W, 2026-W43, 43W, W43, wk43, week 43, 第43週.
_WEEK_PATTERNS = (
    re.compile(r"(?<![0-9A-Za-z])(\d{4})[_\-/ ]?W?(\d{1,2})W(?![0-9A-Za-z])", re.IGNORECASE),
    re.compile(r"(?<![0-9A-Za-z])(\d{4})[_\-/ ]?W(\d{1,2})(?![0-9A-Za-z])", re.IGNORECASE),
    re.compile(r"(?<![0-9A-Za-z_])()(\d{1,2})\s?W(?![0-9A-Za-z])", re.IGNORECASE),
    re.compile(r"(?<![0-9A-Za-z])()(?:W|wk|week)\s?(\d{1,2})(?![0-9A-Za-z])", re.IGNORECASE),
    re.compile(r"()第\s*(\d{1,2})\s*[週周]"),
)
# The example a week field shows: 2026_40W, 2026-W40, 2026W40.
_WEEK_EXAMPLE = re.compile(r"(?<!\d)(\d{4})([_\-]?)(W?)(\d{1,2})(W?)(?![0-9A-Za-z])")
_WEEK_WORD = re.compile(r"week|週|周", re.IGNORECASE)
_DATE = re.compile(r"(?<!\d)(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?!\d)")
_RANGE = re.compile(r"^\s*(?:到|至|~|～|-|–|to|through|until)\s*$", re.IGNORECASE)
_DRY_FIELD = re.compile(r"dry[\s_-]?run|試跑|只看計[畫劃]|預演", re.IGNORECASE)
_DRY_TRUE = re.compile(r"dry[\s_-]?run|只看計[畫劃]|試跑|預演|plan only", re.IGNORECASE)
_DRY_FALSE = re.compile(r"正式|寫入|real run|for real", re.IGNORECASE)
_NEGATION = re.compile(r"(?:不要|不用|別|不|no|not|don'?t)\s*$", re.IGNORECASE)


def _today() -> date:
    """Today on this computer (a test replaces it)."""
    return date.today()


def _texts(field: WorkflowParameter) -> list[str]:
    return [field.label, field.description or "", field.help or "", *field.examples]


def _week_example(field: WorkflowParameter) -> re.Match[str] | None:
    for source in _texts(field):
        found = _WEEK_EXAMPLE.search(source)
        if found is not None:
            return found
    return None


def _week_fields(fields: Iterable[WorkflowParameter]) -> list[tuple[WorkflowParameter, Any]]:
    """Text fields about a week whose example shows its format."""
    found = []
    for field in fields:
        if field.kind != "text" or field.multiple:
            continue
        about = " ".join([field.name, *_texts(field)])
        example = _week_example(field)
        if example is not None and _WEEK_WORD.search(about):
            found.append((field, example))
    return found


def _weeks(text: str, today: date) -> set[tuple[int, int]]:
    """Every distinct (ISO year, week) the text names."""
    found: set[tuple[int, int]] = set()
    taken: list[tuple[int, int]] = []
    for pattern in _WEEK_PATTERNS:
        for match in pattern.finditer(text):
            span = match.span()
            if any(start < span[1] and span[0] < end for start, end in taken):
                continue
            week = int(match.group(2))
            if not 1 <= week <= 53:
                continue
            year = int(match.group(1)) if match.group(1) else today.isocalendar()[0]
            taken.append(span)
            found.add((year, week))
    return found


def _format_week(example: re.Match[str], year: int, week: int) -> str:
    digits = len(example.group(4))
    return f"{year}{example.group(2)}{example.group(3)}{week:0{digits}d}{example.group(5)}"


def _dates(text: str) -> list[tuple[str, tuple[int, int]]]:
    found = []
    for match in _DATE.finditer(text):
        try:
            value = date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            continue
        found.append((value.isoformat(), match.span()))
    return found


def _choice_hits(field: WorkflowParameter, text: str) -> set[str]:
    hits: set[str] = set()
    for choice in field.choices:
        for word in (choice.value, choice.label or ""):
            if len(word) >= 2 and _mentions(text, word):
                hits.add(choice.value)
    if not field.choices:
        for value in field.options:
            if len(value) >= 2 and _mentions(text, value):
                hits.add(value)
    return hits


def _mentions(text: str, word: str) -> bool:
    pattern = r"(?<![0-9A-Za-z_])" + re.escape(word) + r"(?![0-9A-Za-z_])"
    return re.search(pattern, text, re.IGNORECASE) is not None


def _phrase(pattern: re.Pattern[str], text: str) -> bool | None:
    """True when the phrase appears plainly, None when only negated ones do."""
    plain = negated = False
    for match in pattern.finditer(text):
        if _NEGATION.search(text[: match.start()]):
            negated = True
        else:
            plain = True
    return True if plain else None if negated else False


def infer_values(
    manifest: WorkflowManifest,
    text: str,
    fields: Iterable[WorkflowParameter],
    *,
    today: date | None = None,
) -> dict[str, Any]:
    """Unambiguous values for `fields` found in `text` (not yet validated).

    `text` should already have the Workflow's own name and any `name=value`
    pairs removed, so their words are not read as values.
    """
    del manifest  # the fields carry everything this reading uses
    today = today or _today()
    candidates = [item for item in fields if item.kind != "upload"]
    found: dict[str, Any] = {}

    weeks = _week_fields(candidates)
    named = _weeks(text, today)
    if len(weeks) == 1 and len(named) == 1:
        field, example = weeks[0]
        year, week = next(iter(named))
        found[field.name] = _format_week(example, year, week)

    date_fields = [item for item in candidates if item.kind == "date" and not item.multiple]
    dates = _dates(text)
    if len(date_fields) == 1 and len({value for value, _ in dates}) == 1:
        found[date_fields[0].name] = dates[0][0]
    elif len(date_fields) == 2 and len(dates) == 2:
        between = text[dates[0][1][1] : dates[1][1][0]]
        if _RANGE.match(between) and dates[0][0] <= dates[1][0]:
            found[date_fields[0].name] = dates[0][0]
            found[date_fields[1].name] = dates[1][0]

    hits = {
        item.name: _choice_hits(item, text)
        for item in candidates
        if item.kind == "select" and not item.choices_source and not item.multiple
    }
    for name, values in hits.items():
        shared = any(values & other for key, other in hits.items() if key != name)
        if len(values) == 1 and not shared:
            found[name] = next(iter(values))

    switches = [
        item
        for item in candidates
        if item.kind == "boolean" and _DRY_FIELD.search(" ".join([item.name, *_texts(item)]))
    ]
    if len(switches) == 1:
        dry = _phrase(_DRY_TRUE, text)
        real = _phrase(_DRY_FALSE, text)
        if dry is True and real is False:
            found[switches[0].name] = True
        elif real is True and dry is False:
            found[switches[0].name] = False
    return found
