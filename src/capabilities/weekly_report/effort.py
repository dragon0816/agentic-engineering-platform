"""Who worked on what this week, for the weekly mail.

Ported from the pinned source's `_weekly_rules` effort half
(`docs/PHASE_7_MIGRATION.md`, "Workflow 11's mail"). Pure: no I/O, no clock,
no Outlook. What it counts is tickets, not hours, and that is not a shortcut
-- the source verified that every open item carries no worklog and the
project has no points field, so there is no hour data to weigh. The mail says
so on its face.

The source read the instrument from a Jira field and the account from
another. The board that replaced Jira carries both: `Production` holds the
instrument, written exactly as the team writes it, including several on one
ticket (`CMP180, CMX500, WMT2.0, WMT`), and `Company` holds the account.
"""

from __future__ import annotations

import datetime as _dt
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from capabilities.weekly_report.contracts import ReportItem
from capabilities.weekly_report.rules import parse_jira_datetime as parse_datetime

#: What a ticket nobody has assigned, or nothing could be worked out for,
#: is counted under. Kept and shown rather than dropped, and always last so
#: it does not lead a legend.
UNASSIGNED = "Unassigned"

#: Instrument families seen in the team's own summaries. Only a fallback:
#: the board's field is read as written, so a name nobody listed here still
#: shows rather than being forced back to `Unassigned`.
DEFAULT_INSTRUMENTS: tuple[str, ...] = (
    "CMP180",
    "CMP200",
    "CMW100",
    "CMW270",
    "CMW500",
    "CMX500",
    "ZNB3000",
    "ZNB3K",
    "ZNBT",
    "ZNB",
    "ZNA43",
    "ZNA",
    "FSVA",
    "FSW",
    "FSV",
    "FSMR",
    "SMW",
    "SMBV",
    "SMM",
    "SMB",
    "RTO6",
    "RTO",
    "RTB",
    "NRQ6",
    "NRP",
    "OSP",
    "UPV",
)

#: One spelling wins where the team uses two.
DEFAULT_INSTRUMENT_ALIASES: Mapping[str, str] = {"ZNB3K": "ZNB3000"}

#: One ticket routinely covers more than one box, and the field says so with
#: any of these between the names.
INSTRUMENT_SPLIT = re.compile(r"[,;/&+]")


def derive_instrument(
    summary: str,
    instruments: Sequence[str] | None = None,
    aliases: Mapping[str, str] | None = None,
    fallback: str = UNASSIGNED,
) -> str:
    """The instrument a ticket's own title names, longest name first.

    Written into titles both bracketed and bare, so the vocabulary is
    matched anywhere in the text. A model number butts up against `+` and
    `/` in the real data, so the boundary allows a separator and not only a
    word break. A miss is `Unassigned` rather than nothing.
    """
    vocabulary = list(instruments if instruments is not None else DEFAULT_INSTRUMENTS)
    alias_map = dict(DEFAULT_INSTRUMENT_ALIASES if aliases is None else aliases)
    text = summary or ""
    best: tuple[int, int, str] | None = None
    for token in vocabulary:
        pattern = re.compile(rf"(?i)(?<![A-Z0-9]){re.escape(token)}(?![A-Z0-9])")
        found = pattern.search(text)
        if not found:
            continue
        canonical = alias_map.get(token.upper(), token)
        candidate = (-len(token), found.start(), canonical)
        if best is None or candidate < best:
            best = candidate
    return best[2] if best else fallback


def instrument_field(
    item: ReportItem,
    instruments: Sequence[str] | None = None,
    aliases: Mapping[str, str] | None = None,
) -> str:
    """The instrument for one ticket: the board's own field first, the title
    second.

    The field is what the team maintains, and it is right in cases a title
    cannot express. It is taken **as written** rather than filtered through
    the vocabulary above: a field holding `PVT360A` should show that, not be
    forced back to `Unassigned` because the name is unfamiliar. Hiding a real
    answer is the failure this rule exists to prevent.
    """
    written = (item.instrument or "").strip()
    if written:
        return written
    return derive_instrument(item.summary, instruments, aliases)


def instruments_for(
    item: ReportItem,
    instruments: Sequence[str] | None = None,
    aliases: Mapping[str, str] | None = None,
) -> list[str]:
    """Every instrument one ticket is about, in the order written.

    Counting `FSW, SMB` whole invented an instrument of that name with a
    count of one, which then fell below a chart's fold and took both real
    instruments with it. A ticket contributes at most one count per
    instrument, so `FSW, FSW` cannot inflate a total; the deliberate
    consequence is that instrument counts sum to more than the ticket count
    whenever a ticket names two, and the mail says so rather than hiding it.
    """
    label = instrument_field(item, instruments, aliases)
    alias_map = dict(DEFAULT_INSTRUMENT_ALIASES if aliases is None else aliases)
    out: list[str] = []
    for part in INSTRUMENT_SPLIT.split(label):
        part = part.strip()
        if not part:
            continue
        canonical = alias_map.get(part.upper(), part)
        if canonical not in out:
            out.append(canonical)
    return out or [UNASSIGNED]


def account_for(item: ReportItem) -> str:
    """The account a ticket belongs to, as the board records it."""
    return (item.company or "").strip() or UNASSIGNED


def member_for(item: ReportItem) -> str:
    """Who is doing it."""
    return (item.assignee or "").strip() or UNASSIGNED


def _ordered(counts: Mapping[str, int]) -> dict[str, int]:
    """Largest first, `Unassigned` last whatever its size, then by name so
    two runs of the same week read the same."""
    return dict(sorted(counts.items(), key=lambda pair: (pair[0] == UNASSIGNED, -pair[1], pair[0])))


def member_totals(items: Iterable[ReportItem]) -> dict[str, int]:
    """`{member: ticket count}`."""
    counts: dict[str, int] = {}
    for item in items:
        member = member_for(item)
        counts[member] = counts.get(member, 0) + 1
    return _ordered(counts)


def instrument_totals(
    items: Iterable[ReportItem],
    instruments: Sequence[str] | None = None,
    aliases: Mapping[str, str] | None = None,
) -> dict[str, int]:
    """`{instrument: ticket count}` across everybody.

    A ticket naming several instruments counts once under each, so these
    total **at least** the ticket count and never less. Anything showing a
    share divides by the sum of these, not by the number of tickets.
    """
    counts: dict[str, int] = {}
    for item in items:
        for label in instruments_for(item, instruments, aliases):
            counts[label] = counts.get(label, 0) + 1
    return _ordered(counts)


def account_totals(items: Iterable[ReportItem]) -> dict[str, int]:
    """`{account: ticket count}`."""
    counts: dict[str, int] = {}
    for item in items:
        account = account_for(item)
        counts[account] = counts.get(account, 0) + 1
    return _ordered(counts)


def buckets(
    items: Iterable[ReportItem],
    dimension: str = "instrument",
    instruments: Sequence[str] | None = None,
    aliases: Mapping[str, str] | None = None,
) -> dict[str, dict[str, list[str]]]:
    """`{member: {label: [ticket keys]}}`, which is what a chart is drawn
    from and what a table of who-does-what is written from.

    One unit per ticket, with the one exception that a ticket naming several
    instruments is counted once under each, so its key appears in more than
    one bucket. An account is single-valued, as before.
    """
    out: dict[str, dict[str, list[str]]] = {}
    for item in items:
        member = member_for(item)
        if dimension == "instrument":
            labels = instruments_for(item, instruments, aliases)
        else:
            labels = [account_for(item)]
        for label in labels:
            keys = out.setdefault(member, {}).setdefault(label, [])
            if item.key not in keys:
                keys.append(item.key)
    return out


def member_rows(
    items: Iterable[ReportItem],
    instruments: Sequence[str] | None = None,
    aliases: Mapping[str, str] | None = None,
) -> list[dict[str, str]]:
    """One row per ticket, grouped by member, for the mail's first table.

    The instrument is the single-cell view here: a table row names the
    ticket's own field as written, where the counting above splits it.
    """
    rows: list[dict[str, str]] = []
    for item in items:
        rows.append(
            {
                "member": member_for(item),
                "key": item.key,
                "summary": item.summary,
                "account": account_for(item),
                "instrument": instrument_field(item, instruments, aliases),
                "status": item.status,
                "url": item.browse_url or "",
            }
        )
    rows.sort(key=lambda row: (row["member"] == UNASSIGNED, row["member"], row["key"]))
    return rows


@dataclass(frozen=True)
class Activity:
    """Which tickets the mail counts, and which it does not.

    The excluded ones are named rather than counted: a week that goes from
    sixty-three tickets to four without saying which fifty-nine went, and
    why, is indistinguishable from losing them.
    """

    counted: tuple[ReportItem, ...]
    excluded: tuple[str, ...]
    #: Whether the filter was asked for at all.
    required: bool


def commented_in_week(item: ReportItem, since: _dt.date, until: _dt.date) -> bool:
    """Whether somebody wrote on this ticket inside the week itself.

    The week itself, deliberately not the wider comment window a report may
    be configured to paste from: letting that widen who is *counted* would
    move the mail's headline number for a reason nobody reading the setting
    would expect.
    """
    for comment in item.comments:
        written = parse_datetime(comment.created) if comment.created else None
        if written is not None and since <= written.date() <= until:
            return True
    return False


def active_items(
    items: Sequence[ReportItem],
    since: _dt.date,
    until: _dt.date,
    *,
    required: bool = True,
) -> Activity:
    """The tickets somebody worked on this week, in the order given.

    Off, the mail counts everything the week matched, including a ticket
    whose timestamp moved because somebody edited a field. The mail says
    which it did.
    """
    if not required:
        return Activity(counted=tuple(items), excluded=(), required=False)
    counted = [item for item in items if commented_in_week(item, since, until)]
    excluded = [item.key for item in items if item not in counted]
    return Activity(counted=tuple(counted), excluded=tuple(excluded), required=True)
