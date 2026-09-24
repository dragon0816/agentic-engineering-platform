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


def subject(window: ReportingWindow, *, prefix: str = "GTM weekly report") -> str:
    """`GTM weekly report 2026_39W (2026-09-21 .. 2026-09-27)`."""
    return f"{prefix} {window.week} ({window.since:%Y-%m-%d} .. {window.until:%Y-%m-%d})"


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


def build_html(
    window: ReportingWindow,
    items: Sequence[ReportItem],
    *,
    chart_cid: str = "",
    instruments: Sequence[str] | None = None,
    prefix: str = "GTM weekly report",
) -> str:
    """The whole mail, as the HTML a draft carries.

    `chart_cid` is the identifier of an image the draft will attach. Empty
    means there is no picture -- a week where nothing was worked on has
    nothing to draw -- and then the legend's colour column goes too, since a
    colour that keys to no picture is decoration. The numbers are the same
    either way: the chart is a second reading of the table under it, never
    the only place a figure appears.
    """
    parts: list[str] = [
        "<div style='font-family:Segoe UI,Arial,sans-serif;font-size:13px'>",
        f"<h2 style='margin:0 0 4px'>{escape(subject(window, prefix=prefix))}</h2>",
        f"<p style='color:#666;margin:0 0 12px'>{escape(EFFORT_NOTE)}</p>",
        f"<h3 style='margin:16px 0 4px'>Tickets per member ({len(items)})</h3>",
        member_section(items, instruments),
        "<h3 style='margin:16px 0 4px'>Effort by instrument</h3>",
    ]
    totals = effort.instrument_totals(items, instruments)
    if chart_cid:
        parts.append(f"<img src='cid:{escape(chart_cid, quote=True)}' alt='effort by instrument'>")
    parts.append(
        totals_section(
            "Instrument",
            totals,
            note=MULTI_INSTRUMENT_NOTE,
            # The legend, keyed to the picture. Only when there is a picture:
            # a colour column beside no chart is decoration that means nothing.
            colours=chart.colours_for(tuple(totals)) if chart_cid else None,
        )
    )
    parts.append("<h3 style='margin:16px 0 4px'>Effort by account</h3>")
    parts.append(totals_section("Account", effort.account_totals(items)))
    parts.append("</div>")
    return "".join(parts)


def build_text(
    window: ReportingWindow,
    items: Sequence[ReportItem],
    instruments: Sequence[str] | None = None,
) -> str:
    """The same mail as plain text, which is what a plan shows and what a
    person reads when checking a draft before it goes anywhere."""
    lines = [subject(window), "", EFFORT_NOTE, ""]
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
