"""The weekly mail's content, built from the week's items.

Pure: this decides what the mail says and nothing here opens Outlook, draws
anything or touches a file. The drawing and the draft are separate, so what
the mail says can be read, compared and tested without either.

Ported from the pinned source's `jira_weekly_email`
(`docs/PHASE_7_MIGRATION.md`, "Workflow 11's mail"). Two things it says on
its face, because the source insisted on both: effort is a count of tickets
and not of hours, since this project records no hours; and instrument counts
add up to more than the ticket count whenever one ticket names two
instruments.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Mapping, Sequence
from html import escape

from capabilities.weekly_report import chart, effort
from capabilities.weekly_report.contracts import ReportingWindow, ReportItem

#: Said on the mail's face, because a reader who assumes hours would read
#: every number here wrong.
EFFORT_NOTE = (
    "Effort is counted in tickets, not hours: this project records no worklog "
    "and has no points field, so there are no hours to weigh."
)
MULTI_INSTRUMENT_NOTE = (
    "A ticket naming several instruments counts once under each, so instrument "
    "totals add up to more than the number of tickets."
)


def subject(window: ReportingWindow, *, prefix: str = "SDE Weekly Report") -> str:
    """The Outlook subject uses the same week and date range as the body."""
    return f"{prefix} {window.week} ({window.since:%Y-%m-%d} - {window.until:%Y-%m-%d})"


def _cell(text: str) -> str:
    return f"<td style='border:1px solid #d0d0d0;padding:4px 8px'>{escape(text)}</td>"


def _head(text: str) -> str:
    return (
        "<th style='border:1px solid #d0d0d0;padding:4px 8px;"
        f"background:#f0f0f0;text-align:left'>{escape(text)}</th>"
    )


def _table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    if not rows:
        return "<p><i>nothing this week</i></p>"
    head = "".join(_head(name) for name in headers)
    body = "".join("<tr>" + "".join(_cell(value) for value in row) + "</tr>" for row in rows)
    return (
        "<table style='border-collapse:collapse;font-family:Segoe UI,Arial,sans-serif;"
        f"font-size:13px'><tr>{head}</tr>{body}</table>"
    )


def _linked(key: str, url: str) -> str:
    if not url:
        return escape(key)
    return f"<a href='{escape(url, quote=True)}'>{escape(key)}</a>"


def member_section(
    items: Sequence[ReportItem],
    instruments: Sequence[str] | None = None,
) -> str:
    """What each person worked on, one table per person.

    Grouped by member rather than listed flat: the question the mail answers
    is "what is my team doing", and a flat list makes the reader group it.
    """
    rows = effort.member_rows(items, instruments)
    if not rows:
        return "<p><i>nobody worked on anything this week</i></p>"
    out: list[str] = []
    for member in dict.fromkeys(row["member"] for row in rows):
        mine = [row for row in rows if row["member"] == member]
        out.append(f"<h3 style='margin:16px 0 4px'>{escape(member)} ({len(mine)})</h3>")
        out.append(
            _table(
                ["Key", "Summary", "Account", "Instrument", "Status"],
                [
                    [
                        row["key"],
                        row["summary"],
                        row["account"],
                        row["instrument"],
                        row["status"],
                    ]
                    for row in mine
                ],
            )
        )
        # The keys are linked separately, because a table cell escapes its
        # text and a link is not text.
        out[-1] = out[-1].replace(
            _cell(mine[0]["key"]), _cell_link(mine[0]["key"], mine[0]["url"]), 1
        )
        for row in mine[1:]:
            out[-1] = out[-1].replace(_cell(row["key"]), _cell_link(row["key"], row["url"]), 1)
    return "".join(out)


def _cell_link(key: str, url: str) -> str:
    return f"<td style='border:1px solid #d0d0d0;padding:4px 8px'>{_linked(key, url)}</td>"


def _swatch(colour: str) -> str:
    """The chart's colour for this row, as a cell rather than a drawn legend.

    A legend inside the picture would be text nobody can select, text that
    does not wrap on a phone, and text that disappears entirely for a reader
    whose mail client blocks images. Here it is a table, and the numbers
    survive on their own.
    """
    return (
        "<td style='border:1px solid #d0d0d0;padding:4px 8px;width:14px;"
        f"background:{escape(colour, quote=True)}'></td>"
    )


def totals_section(
    title: str,
    totals: Mapping[str, int],
    *,
    note: str = "",
    colours: Mapping[str, str] | None = None,
) -> str:
    """The totals as a table; with `colours`, the legend for the chart above
    it, each row carrying the colour its slice is drawn in."""
    if not totals:
        return "<p><i>nothing this week</i></p>"
    headers = ["", title, "Tickets"] if colours else [title, "Tickets"]
    head = "".join(_head(name) for name in headers)
    body = ""
    for name, count in totals.items():
        cells = _cell(name) + _cell(str(count))
        if colours:
            cells = _swatch(colours.get(name, "#ffffff")) + cells
        body += f"<tr>{cells}</tr>"
    table = (
        "<table style='border-collapse:collapse;font-family:Segoe UI,Arial,sans-serif;"
        f"font-size:13px'><tr>{head}</tr>{body}</table>"
    )
    if note:
        table += f"<p style='color:#666;font-size:12px;margin:4px 0 0'>{escape(note)}</p>"
    return table


def _share_table(title: str, totals: Mapping[str, int]) -> str:
    """Use the source draft's 808px table and aligned 96px numeric columns."""
    denominator = sum(totals.values())
    rows = []
    for label, count in totals.items():
        share = round(count * 100 / denominator) if denominator else 0
        rows.append(
            "<tr>"
            "<td style='padding:6px 10px;border-bottom:1px solid #e1e0d9;"
            f"vertical-align:top'>{escape(label)}</td>"
            "<td align='right' style='padding:6px 10px;border-bottom:1px solid #e1e0d9;"
            "vertical-align:top'>"
            f"{count}</td>"
            "<td align='right' style='padding:6px 10px;border-bottom:1px solid #e1e0d9;"
            f"color:#898781;vertical-align:top'>{share}%</td></tr>"
        )
    rows.append(
        "<tr style='font-weight:600'><td style='padding:8px 10px;border-top:2px solid #52514e'>"
        "合計 (total)</td><td align='right' style='border-top:2px solid #52514e'>"
        f"{denominator}</td>"
        "<td align='right' style='border-top:2px solid #52514e'>"
        f"{'100%' if denominator else '0%'}</td></tr>"
    )
    first = "Instrument" if title == "Instrument totals" else "帳號 (account)"
    count_heading = "Tickets" if title == "Instrument totals" else "張數"
    share_heading = "Share" if title == "Instrument totals" else "佔比"
    th_left = (
        "padding:7px 10px;border-bottom:2px solid #52514e;"
        "font-size:12px;text-align:left;color:#52514e;font-weight:600"
    )
    th_right = th_left.replace("text-align:left", "text-align:right")
    return (
        f"<h3 style='font-size:12px;text-transform:uppercase;color:#52514e'>{escape(title)}</h3>"
        "<table role='presentation' width='808' cellspacing='0' "
        "style='width:808px;max-width:100%;border-collapse:collapse'>"
        f"<tr><th style='{th_left}'>{first}</th>"
        f"<th width='96' style='{th_right}'>{count_heading}</th>"
        f"<th width='96' style='{th_right}'>{share_heading}</th></tr>"
        + "".join(rows) + "</table>"
    )


def _member_split(items: Sequence[ReportItem], instruments: Sequence[str] | None) -> str:
    buckets = effort.buckets(items, instruments=instruments)
    totals = effort.instrument_totals(items, instruments)
    slices = chart.slices_for(totals)
    colours = {name: colour for name, _, colour in slices}
    kept = {name for name in colours if name != "Unassigned" and not name.startswith("Other (")}
    maximum = max(
        (sum(len(keys) for keys in groups.values()) for groups in buckets.values()),
        default=1,
    )
    rows: list[str] = []
    for member in effort.member_totals(items):
        groups = buckets.get(member, {})
        segments = []
        for name, _, colour in slices:
            if name == "Unassigned":
                count = len(groups.get(name, []))
            elif name.startswith("Other ("):
                count = sum(
                    len(keys) for label, keys in groups.items()
                    if label not in kept and label != "Unassigned"
                )
            else:
                count = len(groups.get(name, []))
            if not count:
                continue
            width = max(8, round(300 * count / maximum))
            segments.append(
                f"<td width='{width}' bgcolor='{colour}' title='{escape(name, quote=True)}'"
                " style='height:22px;color:white;text-align:center;font-size:11px'>"
                f"{count if count >= 2 else '&nbsp;'}</td>"
            )
        rows.append(
            "<tr><td style='padding:5px 8px;text-align:right;white-space:nowrap'>"
            f"{escape(member)}</td><td><table cellspacing='1'><tr>{''.join(segments)}"
            "</tr></table></td></tr>"
        )
    legend = " ".join(
        f"<span style='white-space:nowrap;margin-right:10px'>"
        f"<span style='color:{colour}'>■</span> {escape(name)}</span>"
        for name, colour in colours.items()
    )
    return (
        "<div style='font-size:12px;color:#52514e'>Split per team member</div>"
        "<table role='presentation' cellspacing='0'>" + "".join(rows) + "</table>"
        f"<div style='font-size:11px;padding-top:6px'>{legend}</div>"
    )


def build_html(
    window: ReportingWindow,
    items: Sequence[ReportItem],
    *,
    chart_cid: str = "",
    instruments: Sequence[str] | None = None,
    prefix: str = "SDE Weekly Report",
    matched: int | None = None,
    project: str = "",
    activity_required: bool = True,
) -> str:
    """Render the approved Outlook layout from the current week's data."""
    total_matched = len(items) if matched is None else max(matched, len(items))
    instrument_totals = effort.instrument_totals(items, instruments)
    slices = chart.slices_for(instrument_totals)
    displayed_instruments = {name: count for name, count, _ in slices}
    instrument_count = sum(instrument_totals.values())
    account_totals = effort.account_totals(items)
    members = effort.member_totals(items)
    summary = "".join(
        f"<td style='padding-right:14px;white-space:nowrap'><b style='font-size:17px'>{count}</b>"
        f" <span style='color:#898781'>{escape(name)}</span></td>"
        for name, count in members.items()
    )
    activity_label = "本週有留言的" if activity_required else "本週符合條件的"
    excluded = total_matched - len(items)
    if activity_required:
        scope_note = (
            f"一張 ticket 要計入本週，必須在 {window.since:%Y-%m-%d}～"
            f"{window.until:%Y-%m-%d} 之間有新的留言；另有 {excluded} 張"
            "符合查詢但未通過留言條件，因此未計入。"
        )
    else:
        scope_note = "未啟用本週留言篩選；符合查詢條件的 ticket 均計入。"
    empty_note = ""
    if not items:
        reason = (
            f"沒有任何 ticket 在 {window.since:%Y-%m-%d}～{window.until:%Y-%m-%d} "
            f"之間有新的留言；{total_matched} 張符合查詢但未計入。"
            if activity_required else
            f"{window.since:%Y-%m-%d}～{window.until:%Y-%m-%d} 沒有符合條件的 ticket。"
        )
        empty_note = (
            "<tr><td style='padding:16px 26px 0'><div style='background:#fdf6e3;"
            f"border-left:3px solid #d9a441;padding:11px 13px'>{reason}</div></td></tr>"
        )
    instrument_title = (
        f"Tickets by instrument ({instrument_count} total)"
        if instrument_count == len(items) else
        f"Tickets by instrument ({instrument_count} instrument-tickets "
        f"from {len(items)} tickets)"
    )
    image = (
        f"<img src='cid:{escape(chart_cid, quote=True)}' width='300' "
        "alt='Tickets by instrument' style='display:block;max-width:100%;height:auto'>"
        if chart_cid else "<p>No instrument chart this week.</p>"
    )
    project_line = f" &middot; GitHub Project {escape(project)}" if project else ""
    multi_note = (
        "<p style='font-size:11px;color:#898781'>"
        + escape(MULTI_INSTRUMENT_NOTE)
        + f" Share uses {instrument_count} instrument-tickets as its denominator.</p>"
        if instrument_count != len(items) else ""
    )
    return (
        "<html><head><meta http-equiv='Content-Type' "
        "content='text/html; charset=utf-8'></head>"
        "<body style='margin:0;padding:0;background:#f9f9f7'>"
        "<table role='presentation' width='100%' cellspacing='0' style='background:#f9f9f7'>"
        "<tr><td align='center' style='padding:20px 12px'>"
        "<table role='presentation' width='860' cellspacing='0' "
        "style='width:860px;max-width:100%;background:#fcfcfb;border:1px solid #e1e0d9;"
        "font-family:Segoe UI,Calibri,Arial,sans-serif;font-size:13px;color:#0b0b0b'>"
        "<tr><td style='padding:22px 26px 6px'>"
        "<div style='font-size:20px;font-weight:600'>"
        f"{escape(prefix)} &mdash; {escape(window.week)}</div>"
        "<div style='color:#52514e;padding-top:5px'>"
        f"{window.since:%Y-%m-%d} &ndash; {window.until:%Y-%m-%d} &middot; "
        f"{activity_label} <b>{len(items)}</b> / {total_matched} 張{project_line}</div></td></tr>"
        "<tr><td style='padding:12px 26px 0'><div style='background:#f4f6fa;"
        "border-left:3px solid #256bc0;padding:9px 12px;color:#52514e'>"
        "Effort below is a <b>ticket count</b>, not hours: this GitHub project "
        "records no worklog, no time-spent and no story points, so there is no hour data "
        "to report.</div></td></tr>"
        f"{empty_note}"
        "<tr><td style='padding:18px 26px 4px'><b style='font-size:12px;"
        "text-transform:uppercase;color:#52514e'>Tickets per team member</b>"
        "<table role='presentation' cellspacing='0' style='padding-top:8px'>"
        f"<tr>{summary}</tr></table>"
        "</td></tr>"
        "<tr><td style='padding:16px 26px 0'><table role='presentation' width='100%' "
        "cellspacing='0'><tr><td width='45%' valign='top'>"
        f"<div style='font-size:12px;color:#52514e'>{instrument_title}</div>"
        f"{image}</td><td valign='top'>{_member_split(items, instruments)}</td>"
        "</tr></table></td></tr>"
        "<tr><td style='padding:20px 26px 0'>"
        f"{_share_table('Instrument totals', displayed_instruments)}"
        f"{multi_note}"
        "</td></tr><tr><td style='padding:20px 26px 0'>"
        f"{_share_table('Account totals', account_totals)}"
        "</td></tr>"
        "<tr><td style='padding:20px 26px 24px;font-size:11px;color:#898781;"
        "line-height:1.6;border-top:1px solid #e1e0d9'>"
        "Instrument and Account come from the configured GitHub Project fields. "
        "Unknown instrument, member or account values are shown as Unassigned and counted. "
        f"{escape(scope_note)} "
        f"{escape(EFFORT_NOTE)}"
        "</td></tr></table></td></tr></table></body></html>"
    )


def build_text(
    window: ReportingWindow,
    items: Sequence[ReportItem],
    instruments: Sequence[str] | None = None,
    *,
    matched: int | None = None,
    project: str = "",
    prefix: str = "SDE Weekly Report",
) -> str:
    """The same mail as plain text, which is what a plan shows and what a
    person reads when checking a draft before it goes anywhere."""
    total_matched = len(items) if matched is None else matched
    lines = [
        subject(window, prefix=prefix), "",
        f"Counted {len(items)} / {total_matched} tickets", EFFORT_NOTE, "",
    ]
    if project:
        lines.insert(2, f"GitHub Project {project}")
    rows = effort.member_rows(items, instruments)
    for member in dict.fromkeys(row["member"] for row in rows):
        mine = [row for row in rows if row["member"] == member]
        lines.append(f"{member} ({len(mine)})")
        for row in mine:
            summary = row["summary"][:70]
            lines.append(f"  {row['key']:<10} {summary:<70} {row['instrument']}")
        lines.append("")
    lines.append("Effort by instrument")
    for name, count in effort.instrument_totals(items, instruments).items():
        lines.append(f"  {name:<20} {count}")
    lines.append(f"  ({MULTI_INSTRUMENT_NOTE})")
    lines.append("")
    lines.append("Effort by account")
    for name, count in effort.account_totals(items).items():
        lines.append(f"  {name:<20} {count}")
    return "\n".join(lines)


def chart_series(
    items: Sequence[ReportItem], instruments: Sequence[str] | None = None
) -> tuple[tuple[str, ...], tuple[int, ...]]:
    """The labels and counts a pie is drawn from, in the order shown."""
    totals = effort.instrument_totals(items, instruments)
    return tuple(totals), tuple(totals.values())


def drafted_on(today: _dt.date) -> str:
    """The date a draft says it was built, given rather than read."""
    return f"{today:%Y-%m-%d}"
