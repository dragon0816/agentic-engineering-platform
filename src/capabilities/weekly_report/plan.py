"""Working out every row and cell operation before anything is touched.

The source's `build_plan`, typed. The plan is both what a writer executes and
what a dry run shows, so the preview cannot drift from the real behaviour;
and it is what the parity gate grades.
"""

import datetime as _dt
from collections.abc import Sequence

from capabilities.weekly_report import rules
from capabilities.weekly_report.contracts import (
    CommentOperation,
    JiraIssue,
    Remark,
    ReportingWindow,
    SheetState,
    SkippedComment,
    WeeklyReportPlan,
    WeeklyReportSettings,
    WeeklyRow,
)

# How much of a block has to sit at the top of a cell for a recolour to be
# safe: recolouring is by character offset, so a cell somebody typed over
# would get red in the wrong place.
_RECOLOUR_HEAD = 24


def resolve_window(
    settings: WeeklyReportSettings,
    *,
    week: str | None,
    since: _dt.date | None,
    until: _dt.date | None,
    max_issues: int | None,
    today: _dt.date,
) -> ReportingWindow:
    """The week and its window, as the source resolved them: an explicit
    `since`/`until` wins, then the named week's range with either end
    overridable, else the week containing today. The stamp date is today
    when the run is inside the week and the week's end otherwise."""
    name = week or rules.week_name(today, settings.week_style, settings.week_suffix)
    if since is not None and until is not None:
        start, end = since, until
    elif week is not None:
        start, end = rules.week_range_for_name(week, settings.week_style)
        start = since if since is not None else start
        end = until if until is not None else end
    else:
        start, end = rules.week_range(today)
        start = since if since is not None else start
        end = until if until is not None else end
    stamp = min(today, end) if today >= start else end
    lookback = settings.lookback_days
    comment_since = start - _dt.timedelta(days=lookback) if lookback else start
    cap = max_issues if max_issues is not None else settings.max_issues
    return ReportingWindow(
        week=name,
        since=start,
        until=end,
        comment_since=comment_since,
        stamp_date=stamp,
        jql=rules.compose_jql(settings.base_jql(), rules.jql_updated_clause(start, end)),
        max_issues=cap,
    )


def build_plan(
    settings: WeeklyReportSettings,
    window: ReportingWindow,
    issues: Sequence[JiraIssue],
    sheet: SheetState,
    *,
    capped: bool = False,
) -> WeeklyReportPlan:
    """Every row and cell operation, decided from the issues and the sheet.

    A ticket the sheet has never seen earns a row only by actually being
    worked on: without marker content this week it is skipped, so a brand-new
    ticket, or one dormant for months, does not arrive on the strength of a
    field edit alone. A row already in the sheet is always refreshed, so
    nothing the user is tracking silently stops updating."""
    sales_header = rules.resolve_sales_header(sheet.headers)
    rows: list[WeeklyRow] = []
    operations: list[CommentOperation] = []
    remarks: list[Remark] = []
    skipped: list[SkippedComment] = []
    for issue in issues:
        thread = [{"created": item.created, "body": item.body} for item in issue.comments]
        blocks = rules.extract_week_blocks(
            thread, window.comment_since, window.until, settings.markers
        )
        text = rules.format_comment_block(
            window.stamp_date, blocks, settings.bullet, settings.zero_pad_date
        )
        present = issue.key in sheet.existing
        if not text and not present:
            skipped.append(
                SkippedComment(
                    key=issue.key, reason="not in the sheet and no comment content this week"
                )
            )
            continue
        rows.append(
            WeeklyRow(
                key=issue.key,
                summary=issue.summary,
                company=issue.company,
                status=issue.status,
                assignee=issue.assignee or rules.UNASSIGNED,
                sales=issue.sales,
            )
        )
        if not text:
            skipped.append(
                SkippedComment(key=issue.key, reason="no marker-tagged comment content in window")
            )
            continue
        current = sheet.existing.get(issue.key)
        if not rules.should_prepend(current, text):
            # Already in the cell, so there is nothing to add; but the reset
            # at the start of a run turns it black, so it is recoloured
            # rather than left looking untouched, when it really does still
            # open with this block.
            skipped.append(
                SkippedComment(
                    key=issue.key, reason="identical block already present (idempotent skip)"
                )
            )
            if (current or "").lstrip().startswith(text.strip()[:_RECOLOUR_HEAD]):
                remarks.append(Remark(key=issue.key, text=text))
            continue
        operations.append(
            CommentOperation(
                key=issue.key,
                text=text,
                markers=tuple(block.marker for block in blocks),
                line_count=sum(len(block.lines) for block in blocks),
            )
        )
    new_keys = tuple(row.key for row in rows if row.key not in sheet.existing)
    updated_keys = tuple(row.key for row in rows if row.key in sheet.existing)
    # Tinted: gained content this week, already holds this week's content,
    # or arrived this week. All three are "this week", which is what the tint
    # claims to mean, and the second is why running twice in a week used to
    # wipe the marks the first run made.
    tinted: list[str] = [op.key for op in operations]
    for key in [remark.key for remark in remarks] + list(new_keys):
        if key not in tinted:
            tinted.append(key)
    plan = WeeklyReportPlan(
        window=window,
        sales_header=sales_header,
        rows=tuple(rows),
        new_keys=new_keys,
        updated_keys=updated_keys,
        comment_operations=tuple(operations),
        remarks=tuple(remarks),
        skipped=tuple(skipped),
        highlight_keys=tuple(tinted),
        issue_keys=tuple(sorted({issue.key for issue in issues})),
        capped=capped,
        sheet_digest=sheet.digest,
        preview="pending",
    )
    return plan.model_copy(update={"preview": render_preview(settings, plan, sheet)})


def render_preview(
    settings: WeeklyReportSettings, plan: WeeklyReportPlan, sheet: SheetState
) -> str:
    """The planned operations as the source's dry run printed them: what
    would be written, in order, and nothing written."""
    headers = sheet.headers or rules.WEEKLY_COLUMNS
    try:
        key_col = rules.column_for_header(headers, "Key")
        comment_col = rules.column_for_header(headers, "Comments")
    except KeyError:
        key_col, comment_col = "A", "G"
    try:
        status_col: str | None = rules.column_for_header(headers, "Status")
    except KeyError:
        status_col = None
    last_col = rules.column_letter(len(headers))
    window = plan.window
    lines = [
        "# Planned Excel operations -- DRY RUN, nothing was written",
        f"# workbook : {settings.workbook_path}",
        f"# sheet    : {settings.temp_sheet}",
        f"# week     : {window.week}  ({window.since} .. {window.until})",
        f"# seed     : {sheet.seed_sheet}",
        f"# before   : {plan.sheet_digest}",
        *(
            [
                f"# CAPPED   : the search stopped at {window.max_issues} issue(s); "
                "this is not the whole week"
            ]
            if plan.capped
            else []
        ),
        "",
        f"1) copy '{sheet.seed_sheet}' -> '{settings.temp_sheet}' (only if the sheet is missing)",
        f"2) upsert by Key  rows={len(plan.rows)}"
        f"  (new={len(plan.new_keys)}, update={len(plan.updated_keys)})",
        f"3) read {status_col or '-'}1:{status_col or '-'}<last> fills"
        f"   <- find last week's {settings.new_row_fill} to retire; other colours are left alone",
        f"4) RESET: font {comment_col}2:{comment_col}<last> = {settings.comment_tail_color},"
        f"  clearFill {key_col}2:{key_col}<last>, clearFill each stale {settings.new_row_fill}"
        "   <- retires last week's marks; repaints rows this run does not touch",
        f"5) fill {key_col}<row> = {settings.key_highlight}"
        f"  x{len(plan.highlight_keys)}   <- new comment content, or a new row",
        f"6) new rows: border A<row>:{last_col}<row> style={settings.new_row_border}"
        + (
            f", fill {status_col}<row> = {settings.new_row_fill}"
            if status_col and settings.new_row_border != "none"
            else ""
        )
        + f"  x{len(plan.new_keys)}",
        f"7) rich-prepend {comment_col}<row> color={settings.comment_color} dedupe=true"
        f"  x{len(plan.comment_operations)}",
        "",
        "-- new rows ------------------------------------------------------",
    ]
    lines += [f"   + {key}" for key in plan.new_keys] or ["   (none)"]
    lines += ["", "-- updated rows --------------------------------------------------"]
    lines += [f"   ~ {key}" for key in plan.updated_keys] or ["   (none)"]
    lines += ["", "-- comment blocks to prepend (red, newest on top) ----------------"]
    for op in plan.comment_operations:
        lines.append(f"   {op.key}  markers={','.join(op.markers)}  lines={op.line_count}")
        lines.extend(f"        | {line}" for line in op.text.rstrip("\n").split("\n"))
        lines.append("")
    if not plan.comment_operations:
        lines.append("   (none)")
    lines += ["", "-- comment blocks skipped ----------------------------------------"]
    lines += [f"   {item.key}: {item.reason}" for item in plan.skipped] or ["   (none)"]
    return "\n".join(lines) + "\n"
