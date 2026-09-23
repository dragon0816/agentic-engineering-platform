"""Pure rules for the weekly report. No I/O, no network, no workbook.

Ported as they stand from the pinned Host Bridge's `_weekly_rules`
(`docs/PHASE_7_MIGRATION.md`, "Workflow 7"). Every rule here was derived
from the real workbook and the real project, not invented, and the source's
own tests are the oracle for this port:

* `SDE_Weekly_Report.xlsx`: weekly sheets named `YYYY_NW`, a `Comments` cell
  holding a newest-first dated log in `M/D:` / `- line` form, the newest block
  a red run and the older text black.
* Jira project GTM on Atlassian Cloud: `customfield_10093` is *Company*,
  `customfield_10094` is *Salse* (misspelt in Jira itself), `customfield_10019`
  is *Rank*, `customfield_10052` is *Category*.

What is deliberately not ported: the email job's effort, instrument, chipset
and account derivations, which belong to a different entry point.
"""

import datetime as _dt
import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

WeekStyle = Literal["iso", "us", "iso-1"]

# ---------------------------------------------------------------------------
# Excel column contract
# ---------------------------------------------------------------------------

#: Header row of a weekly sheet, in order. 71 of the 75 sheets in the live
#: workbook spell column F `Sales`; three legacy 2025 sheets spell it `Salse`.
#: The job always prefers the header it actually reads from the seed sheet.
WEEKLY_COLUMNS: tuple[str, ...] = (
    "Key",
    "Summary",
    "Company",
    "Status",
    "Assignee",
    "Sales",
    "Comments",
)

#: Legacy spelling kept so upserts against an old sheet still find column F.
SALES_COLUMN_ALIASES: tuple[str, ...] = ("Sales", "Salse")

#: Jira custom fields observed on project GTM.
FIELD_COMPANY = "customfield_10093"
FIELD_SALES = "customfield_10094"  # named "Salse" in Jira
FIELD_RANK = "customfield_10019"  # cf[10019] in the user's JQL == Rank (LexoRank)
FIELD_CATEGORY = "customfield_10052"
FIELD_INSTRUMENT = "customfield_10260"

#: Fields the report needs from a search.
REPORT_FIELDS: tuple[str, ...] = (
    "summary",
    "status",
    "assignee",
    "updated",
    "created",
    "labels",
    "comment",
    FIELD_COMPANY,
    FIELD_SALES,
    FIELD_RANK,
    FIELD_CATEGORY,
    FIELD_INSTRUMENT,
)

UNASSIGNED = "Unassigned"

DEFAULT_PROJECT = "GTM"
DEFAULT_STATUSES: tuple[str, ...] = ("In Progress", "Ready for Launch", "To Do", "Pending")


def default_jql(project: str = DEFAULT_PROJECT, statuses: Sequence[str] = DEFAULT_STATUSES) -> str:
    """The base JQL the source built when the config named none: the board's
    own order, by `updated` and then by rank."""
    quoted = ", ".join(f'"{status}"' for status in statuses)
    return f"project = {project} AND status in ({quoted}) ORDER BY updated DESC, cf[10019] ASC"


# ---------------------------------------------------------------------------
# Week naming and ranges
# ---------------------------------------------------------------------------

_WEEK_NAME_RE = re.compile(r"^(?P<year>20\d{2})_(?P<num>\d{1,2})(?P<suffix>W?)$")


def parse_week_name(name: str | None) -> tuple[int, int] | None:
    """`(year, week_number)` for a weekly sheet name. Tolerates the workbook's
    irregularities: `2025_14` has no trailing `W` and is still weekly."""
    match = _WEEK_NAME_RE.match((name or "").strip())
    if not match:
        return None
    return int(match.group("year")), int(match.group("num"))


def is_weekly_sheet(name: str) -> bool:
    return parse_week_name(name) is not None


def week_number(day: _dt.date, style: WeekStyle = "iso") -> tuple[int, int]:
    """`(year, week_number)` under the given numbering style.

    `iso` is ISO-8601 (weeks start Monday, week 1 holds the first Thursday);
    `us` is `%W` (week 1 begins at the first Monday, earlier days are week 0);
    `iso-1` is the ISO week minus one, clamped at 1, which is how the newest
    sheets in the workbook are actually numbered. The live workbook is
    inconsistent, so `iso` is the default and the style is configurable."""
    if style == "iso":
        calendar = day.isocalendar()
        return calendar[0], calendar[1]
    if style == "us":
        return day.year, int(day.strftime("%W"))
    if style == "iso-1":
        calendar = day.isocalendar()
        return calendar[0], max(1, calendar[1] - 1)
    raise ValueError(f"unknown week style: {style!r}")


def week_name(day: _dt.date, style: WeekStyle = "iso", suffix: str = "W") -> str:
    year, number = week_number(day, style)
    return f"{year}_{number}{suffix}"


def week_range(day: _dt.date) -> tuple[_dt.date, _dt.date]:
    """Monday..Sunday (inclusive) of the week containing `day`. The numbering
    style changes the label, not the calendar boundaries."""
    monday = day - _dt.timedelta(days=day.weekday())
    return monday, monday + _dt.timedelta(days=6)


def week_range_for_name(name: str, style: WeekStyle = "iso") -> tuple[_dt.date, _dt.date]:
    """Monday..Sunday for a `YYYY_NW` sheet name under `style`."""
    parsed = parse_week_name(name)
    if parsed is None:
        raise ValueError(f"not a weekly sheet name: {name!r}")
    year, number = parsed
    if style == "iso":
        monday = _dt.date.fromisocalendar(year, number, 1)
    elif style == "iso-1":
        # Week N under iso-1 is ISO week N+1, which for the last week of a
        # 52-week year is the first week of the next: a week later, not
        # a week number the calendar refuses.
        monday = _dt.date.fromisocalendar(year, number, 1) + _dt.timedelta(weeks=1)
    elif style == "us":
        first = _dt.date(year, 1, 1)
        first_monday = first + _dt.timedelta(days=(7 - first.weekday()) % 7)
        monday = first_monday + _dt.timedelta(weeks=number - 1)
    else:
        raise ValueError(f"unknown week style: {style!r}")
    return monday, monday + _dt.timedelta(days=6)


def jql_updated_clause(start: _dt.date, end: _dt.date) -> str:
    """Issues updated within `start`..`end` inclusive. Jira's `updated <=
    "yyyy-MM-dd"` means midnight at the start of that day, so the upper bound
    is the day after `end`."""
    upper = end + _dt.timedelta(days=1)
    return f'updated >= "{start:%Y-%m-%d}" AND updated < "{upper:%Y-%m-%d}"'


_ORDER_BY_RE = re.compile(r"(?i)\border\s+by\b")


def compose_jql(base_jql: str, *clauses: str) -> str:
    """Add `AND`-ed clauses to a JQL string, keeping its `ORDER BY` last."""
    extra = [clause.strip() for clause in clauses if clause and clause.strip()]
    base = (base_jql or "").strip()
    if not extra:
        return base
    match = _ORDER_BY_RE.search(base)
    if match:
        head, tail = base[: match.start()].strip(), base[match.start() :].strip()
    else:
        head, tail = base, ""
    added = " AND ".join(f"({clause})" for clause in extra)
    head = f"{head} AND {added}" if head else added
    return f"{head} {tail}".strip()


def column_letter(index: int) -> str:
    """1-based column index to an Excel column letter."""
    if index < 1:
        raise ValueError("column index is 1-based")
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def column_for_header(headers: Sequence[str], name: str) -> str:
    """Excel column letter for a header name (case-insensitive, alias-aware)."""
    targets = {name.strip().lower()}
    if name.strip().lower() in {"sales", "salse"}:
        targets = {"sales", "salse"}
    for index, header in enumerate(headers, start=1):
        if str(header).strip().lower() in targets:
            return column_letter(index)
    raise KeyError(f"header {name!r} not found in {list(headers)!r}")


def latest_weekly_sheet(
    sheet_names: Sequence[str], before: tuple[int, int] | None = None
) -> str | None:
    """The sheet to seed the scratch sheet from, chosen by `(year, week)`
    rather than workbook position: the workbook has hand-made gaps and one
    misnamed sheet. `before` excludes that week and everything after it, so a
    run for week 32 never seeds from the `2026_32W` the user made by hand."""
    best: tuple[int, int, int] | None = None
    best_name: str | None = None
    for index, name in enumerate(sheet_names):
        parsed = parse_week_name(name)
        if parsed is None:
            continue
        if before is not None and (parsed[0], parsed[1]) >= before:
            continue
        candidate = (parsed[0], parsed[1], index)
        if best is None or candidate > best:
            best, best_name = candidate, name
    return best_name


# ---------------------------------------------------------------------------
# Comment bodies: ADF and plain text
# ---------------------------------------------------------------------------

_ADF_BLOCK_TYPES = {
    "paragraph",
    "heading",
    "blockquote",
    "codeBlock",
    "panel",
    "listItem",
    "tableRow",
    "rule",
}


def adf_to_text(node: Any) -> str:
    """Flatten an Atlassian Document Format node to plain text. The Cloud
    REST API returns comment bodies as ADF; API v2 returns plain strings;
    both reach this module. Bullet items render as `- item`, which is how the
    workbook's `Comments` cells are written by hand."""
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(item) for item in node)
    if not isinstance(node, Mapping):
        return str(node)
    kind = node.get("type")
    if kind == "text":
        return str(node.get("text", ""))
    if kind in ("hardBreak", "rule"):
        return "\n"
    if kind == "mention":
        attrs = node.get("attrs") or {}
        return str(attrs.get("text") or attrs.get("displayName") or "")
    if kind == "emoji":
        attrs = node.get("attrs") or {}
        return str(attrs.get("text") or attrs.get("shortName") or "")
    if kind == "inlineCard":
        attrs = node.get("attrs") or {}
        return str(attrs.get("url") or "")
    inner = adf_to_text(node.get("content"))
    if kind == "listItem":
        body = inner.strip("\n")
        lines = body.split("\n")
        if not lines or not any(line.strip() for line in lines):
            return ""
        head, *rest = lines
        return "\n".join([f"- {head}", *rest]) + "\n"
    if kind in ("bulletList", "orderedList"):
        return inner
    if kind in _ADF_BLOCK_TYPES or kind in ("doc", "tableCell", "tableHeader", "table"):
        if inner and not inner.endswith("\n"):
            inner += "\n"
        return inner
    return inner


def comment_body_text(body: Any) -> str:
    """A comment body (ADF or plain) as clean text: NBSP and CRLF normalised,
    runs of blank lines collapsed, so marker parsing and dedupe are stable."""
    text = adf_to_text(body)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace(" ", " ").replace("​", "")
    text = unicodedata.normalize("NFC", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Marker extraction
# ---------------------------------------------------------------------------

#: Canonical marker buckets, in the order they should appear in the cell.
CANONICAL_MARKERS: tuple[str, ...] = ("Completed", "In-progress", "In-Completed", "Todo")

#: Canonical marker -> synonyms actually observed in the live data. The four
#: bracketed markers are the intended vocabulary; the team mostly writes
#: free-form headers (`ongoing task:` 47 times in one week's comments), so
#: the defaults cover both and everything is overridable.
DEFAULT_MARKER_SYNONYMS: dict[str, tuple[str, ...]] = {
    "Completed": (
        "completed",
        "complete",
        "completed task",
        "completed tasks",
        "complete task",
        "complete tasks",
        "complete items",
        "completed items",
        "completed result",
        "done",
    ),
    "In-progress": (
        "in-progress",
        "in progress",
        "inprogress",
        "ongoing",
        "on-going",
        "ongoing task",
        "ongoing tasks",
        "on-going task",
        "on-going tasks",
        "in-progress task",
        "in-progress tasks",
    ),
    "In-Completed": (
        "in-completed",
        "in completed",
        "incompleted",
        "incomplete",
        "in-complete",
        "in-completed task",
        "in-completed tasks",
        "not completed",
    ),
    "Todo": (
        "todo",
        "to do",
        "to-do",
        "next step",
        "next steps",
        "next setp",  # observed typo, kept deliberately
        "pending",
        "plan",
    ),
}


@dataclass(frozen=True)
class MarkerBlock:
    """One marker section extracted from a comment. `day` is the date of the
    comment it came from, which is what lets the workbook stamp each block
    with the day it was written rather than the day the job ran."""

    marker: str
    raw_marker: str
    lines: tuple[str, ...]
    day: _dt.date | None = None

    def as_text(self, bullet: str = "- ") -> str:
        head = f"[{self.marker}]"
        if not self.lines:
            return head
        body = "\n".join(f"{bullet}{line}" for line in self.lines)
        return f"{head}\n{body}"


def _normalise_marker(token: str) -> str:
    return re.sub(r"[\s_]+", " ", token.strip().lower()).strip(" :#[]-")


def build_marker_lookup(synonyms: Mapping[str, Iterable[str]] | None = None) -> dict[str, str]:
    """`normalised synonym -> canonical marker`."""
    table = synonyms if synonyms is not None else DEFAULT_MARKER_SYNONYMS
    lookup: dict[str, str] = {}
    for canonical, words in table.items():
        lookup[_normalise_marker(canonical)] = canonical
        for word in words:
            lookup[_normalise_marker(word)] = canonical
    return lookup


def build_marker_pattern(lookup: Mapping[str, str]) -> re.Pattern[str]:
    """A marker header is a short line, not prose: the whole line (optionally
    bracketed, hashed or bulleted) or followed immediately by a colon. That
    keeps `Complete the rest of test item OBUE` from being a header while
    `Complete tasks: got the request` still is. Longest synonyms win."""
    alternatives = sorted((re.escape(key) for key in lookup if key), key=len, reverse=True)
    if not alternatives:
        # No vocabulary matches nothing; an empty alternation would match
        # every blank line.
        return re.compile(r"(?!x)x(?P<marker>)(?P<inline>)")
    body = "|".join(alternatives)
    return re.compile(
        r"(?im)^[ \t]*[-*#>•]*[ \t]*"
        r"\[?[ \t]*"
        rf"(?P<marker>{body})"
        r"[ \t]*\]?"
        r"[ \t]*(?:[:：]|$)"
        r"(?P<inline>[^\n]*)$",
    )


_DATE_HEADER_RE = re.compile(r"(?m)^[ \t]*(\d{1,2})\s*/\s*(\d{1,2})[ \t]*:?[ \t]*$")
_BULLET_RE = re.compile(r"^[ \t]*(?:[-*•]+|\d+[.)])[ \t]*")
#: A kept line must contain at least one letter, digit or CJK character.
_SUBSTANCE_RE = re.compile(r"[\w一-鿿]")


def _clean_lines(chunk: str) -> tuple[str, ...]:
    out: list[str] = []
    for raw in chunk.split("\n"):
        line = _BULLET_RE.sub("", raw).strip()
        if not line or _DATE_HEADER_RE.match(raw):
            continue
        out.append(line)
    return tuple(out)


def extract_marker_blocks(
    body: Any,
    synonyms: Mapping[str, Iterable[str]] | None = None,
    max_lines_per_block: int = 20,
) -> list[MarkerBlock]:
    """Only the marker-tagged sections of one comment body. Content for a
    marker runs from its header to the next marker, the next `M/D:` date
    header, or the end; untagged prose is dropped, which is the point. A date
    header at the very top of a block is the block's own date line (half the
    team writes the date under the marker) and is dropped, not a terminator."""
    text = comment_body_text(body)
    if not text:
        return []
    lookup = build_marker_lookup(synonyms)
    pattern = build_marker_pattern(lookup)
    matches = list(pattern.finditer(text))
    if not matches:
        return []
    blocks: list[MarkerBlock] = []
    for index, match in enumerate(matches):
        canonical = lookup[_normalise_marker(match.group("marker"))]
        stop = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        chunk = text[match.end() : stop]
        leading = _DATE_HEADER_RE.match(chunk.lstrip("\n"))
        if leading:
            chunk = chunk.lstrip("\n")[leading.end() :]
        date_stop = _DATE_HEADER_RE.search(chunk)
        if date_stop:
            chunk = chunk[: date_stop.start()]
        lines: list[str] = []
        inline = (match.group("inline") or "").strip()
        if inline:
            lines.append(_BULLET_RE.sub("", inline).strip())
        lines.extend(_clean_lines(chunk))
        deduped: list[str] = []
        for line in lines:
            # "[Completed] :" leaves a lone ":" behind, which would render as
            # a bullet reading "- :" (seen on GTM-765).
            if line and _SUBSTANCE_RE.search(line) and line not in deduped:
                deduped.append(line)
        if not deduped:
            continue
        blocks.append(
            MarkerBlock(
                marker=canonical,
                raw_marker=match.group("marker").strip(),
                lines=tuple(deduped[:max_lines_per_block]),
            )
        )
    return blocks


def merge_marker_blocks(blocks: Iterable[MarkerBlock]) -> list[MarkerBlock]:
    """Collapse blocks sharing a canonical marker on the same day. Days come
    out newest first; markers within a day keep canonical order; blocks with
    no day share one group, which is the older behaviour."""
    order: list[tuple[_dt.date | None, str]] = []
    grouped: dict[tuple[_dt.date | None, str], list[str]] = {}
    raws: dict[tuple[_dt.date | None, str], str] = {}
    for block in blocks:
        key = (block.day, block.marker)
        if key not in grouped:
            grouped[key] = []
            order.append(key)
            raws[key] = block.raw_marker
        for line in block.lines:
            if line not in grouped[key]:
                grouped[key].append(line)

    def sort_key(key: tuple[_dt.date | None, str]) -> tuple[Any, ...]:
        day, marker = key
        return (
            0 if day is None else 1,
            -day.toordinal() if day else 0,
            CANONICAL_MARKERS.index(marker) if marker in CANONICAL_MARKERS else 99,
            marker,
        )

    order.sort(key=sort_key)
    return [MarkerBlock(m, raws[(d, m)], tuple(grouped[(d, m)]), d) for d, m in order]


# ---------------------------------------------------------------------------
# Comment windows
# ---------------------------------------------------------------------------


def parse_jira_datetime(value: str | None) -> _dt.datetime | None:
    """Jira's `2026-07-28T14:30:55.627+0800` timestamps, and the `Z` form."""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    match = re.match(r"^(.*)([+-]\d{2})(\d{2})$", text)
    if match and ":" not in text[-6:]:
        text = f"{match.group(1)}{match.group(2)}:{match.group(3)}"
    try:
        return _dt.datetime.fromisoformat(text)
    except ValueError:
        return None


def _comment_created(comment: Mapping[str, Any]) -> _dt.datetime | None:
    raw = comment.get("created") or comment.get("updated")
    return parse_jira_datetime(str(raw)) if raw else None


def select_comments_in_window(
    comments: Sequence[Mapping[str, Any]],
    start: _dt.date | None = None,
    end: _dt.date | None = None,
) -> list[Mapping[str, Any]]:
    """Comments created within `start`..`end` inclusive, oldest first, in the
    timestamp's own offset. Comments without a parsable timestamp are kept:
    dropping content is worse than including a little extra in a sheet the
    user hand-edits anyway."""
    picked: list[tuple[_dt.datetime, Mapping[str, Any]]] = []
    undated: list[Mapping[str, Any]] = []
    for comment in comments:
        created = _comment_created(comment)
        if created is None:
            undated.append(comment)
            continue
        day = created.date()
        if start is not None and day < start:
            continue
        if end is not None and day > end:
            continue
        picked.append((created, comment))
    picked.sort(key=lambda pair: pair[0])
    return [comment for _, comment in picked] + undated


def extract_week_blocks(
    comments: Sequence[Mapping[str, Any]],
    start: _dt.date | None = None,
    end: _dt.date | None = None,
    synonyms: Mapping[str, Iterable[str]] | None = None,
) -> list[MarkerBlock]:
    """All marker blocks from the comments inside the week, each carrying the
    day of the comment it came from, merged per day."""
    blocks: list[MarkerBlock] = []
    for comment in select_comments_in_window(comments, start, end):
        created = _comment_created(comment)
        day = created.date() if created else None
        for block in extract_marker_blocks(comment.get("body"), synonyms):
            blocks.append(MarkerBlock(block.marker, block.raw_marker, block.lines, day))
    return merge_marker_blocks(blocks)


# ---------------------------------------------------------------------------
# Comment cell formatting and idempotency
# ---------------------------------------------------------------------------


def format_date_header(day: _dt.date, zero_pad: bool = False) -> str:
    """`7/28:`, the workbook's own style; unpadded is the dominant form."""
    if zero_pad:
        return f"{day.month:02d}/{day.day:02d}:"
    return f"{day.month}/{day.day}:"


def format_comment_block(
    day: _dt.date,
    blocks: Sequence[MarkerBlock],
    bullet: str = "- ",
    zero_pad: bool = False,
) -> str:
    """The block prepended to a `Comments` cell: one header per distinct
    comment date, newest first, each followed by its markers. `day` is the
    fallback for blocks whose comment had no parsable timestamp. Empty when
    there is nothing marker-tagged, which the plan treats as "leave the cell
    alone"."""
    if not blocks:
        return ""
    by_day: dict[_dt.date, list[MarkerBlock]] = {}
    for block in blocks:
        by_day.setdefault(block.day or day, []).append(block)
    parts: list[str] = []
    for when in sorted(by_day, reverse=True):
        parts.append(format_date_header(when, zero_pad))
        for block in by_day[when]:
            parts.append(block.as_text(bullet))
    return "\n".join(parts) + "\n"


def normalise_for_dedupe(text: str | None) -> str:
    """Whitespace- and case-insensitive form used to compare blocks."""
    value = (text or "").replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    lines = [re.sub(r"\s+", " ", line).strip().lower() for line in value.split("\n")]
    return "\n".join(line for line in lines if line)


def should_prepend(existing: str | None, new_block: str) -> bool:
    """The idempotency guard: skip when there is nothing to add, when the
    cell already starts with the same normalised block, or when the identical
    block already appears anywhere in it (a re-run after the user hand-added a
    newer entry on top)."""
    if not (new_block or "").strip():
        return False
    old = normalise_for_dedupe(existing)
    new = normalise_for_dedupe(new_block)
    if not new:
        return False
    if not old:
        return True
    if old.startswith(new):
        return False
    return new not in old


# ---------------------------------------------------------------------------
# Row building
# ---------------------------------------------------------------------------


def display(value: Any) -> str:
    """A Jira field as the cell shows it: a named object's display name, a
    list joined by commas, nothing for None."""
    if value is None:
        return ""
    if isinstance(value, Mapping):
        for key in ("displayName", "name", "value"):
            if value.get(key):
                return str(value[key])
        return ""
    if isinstance(value, list | tuple):
        return ", ".join(part for part in (display(item) for item in value) if part)
    return str(value)


def issue_to_row(issue: Mapping[str, Any], sales_header: str = "Sales") -> dict[str, str]:
    """A Jira issue as a weekly-sheet row. `Comments` is deliberately absent:
    it is a hand-maintained log and is only ever prepended to."""
    fields = issue.get("fields") or {}
    return {
        "Key": str(issue.get("key") or ""),
        "Summary": display(fields.get("summary")),
        "Company": display(fields.get(FIELD_COMPANY)),
        "Status": display(fields.get("status")),
        "Assignee": display(fields.get("assignee")) or UNASSIGNED,
        sales_header: display(fields.get(FIELD_SALES)),
    }


def resolve_sales_header(headers: Sequence[str] | None) -> str:
    """Whichever spelling of the Sales column the sheet actually uses."""
    for header in headers or ():
        if str(header).strip() in SALES_COLUMN_ALIASES:
            return str(header).strip()
    return "Sales"
