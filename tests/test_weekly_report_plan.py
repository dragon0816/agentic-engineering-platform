"""The weekly report's plan: which rows reach the workbook and what the red
text and the yellow tint mean.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 3a. The cases are the
pinned Host Bridge's `test_weekly_report_plan.py`, which were written for
the things that were quietly wrong: red that survived on rows never touched,
a tint on every JQL match, and the run date stamped on work written up on
another day. No Jira, no workbook.
"""

import datetime as _dt
import hashlib
from typing import Any

import pytest
from pydantic import ValidationError

from capabilities.weekly_report.contracts import (
    JiraComment,
    JiraIssue,
    ReportingWindow,
    SheetState,
    WeeklyReportPlan,
    WeeklyReportRequest,
    WeeklyReportSettings,
    WeeklyRow,
)
from capabilities.weekly_report.plan import build_plan, resolve_window

START, END = _dt.date(2026, 7, 27), _dt.date(2026, 8, 2)
RUN_DATE = _dt.date(2026, 8, 1)
EMPTY_DIGEST = hashlib.sha256(b"[[], []]").hexdigest()


def settings(**changes: Any) -> WeeklyReportSettings:
    return WeeklyReportSettings.model_validate(
        {"workbook_path": "C:/Users/someone/Report/SDE_Weekly_Report.xlsx", **changes}
    )


def window(**changes: Any) -> ReportingWindow:
    return resolve_window(
        settings(), week="2026_31W", since=None, until=None, max_issues=None, today=RUN_DATE
    ).model_copy(update=changes)


def sheet(existing: dict[str, str] | None = None, **changes: Any) -> SheetState:
    return SheetState.model_validate(
        {
            "headers": ["Key", "Summary", "Company", "Status", "Assignee", "Sales", "Comments"],
            "existing": existing or {},
            "scratch_present": True,
            "source_sheet": "weekly report temp",
            "digest": EMPTY_DIGEST,
            **changes,
        }
    )


def comment(created: str, body: str) -> JiraComment:
    return JiraComment(created=created, body=body)


def issue(key: str, *comments: JiraComment, summary: str = "[WNC] work") -> JiraIssue:
    return JiraIssue(
        key=key,
        summary=summary,
        status="In Progress",
        assignee="Ming-Kai Shih",
        comments=comments,
    )


WORKED_ON = issue("GTM-1", comment("2026-07-29T09:00:00.000+0800", "completed:\n- tx cal"))
FIELD_TOUCH_ONLY = issue("GTM-688", comment("2026-07-25T16:57:19.442+0800", "completed:\n- old"))
SILENT = issue("GTM-455")


def plan_for(
    issues: list[JiraIssue], existing: dict[str, str] | None = None, **changes: Any
) -> WeeklyReportPlan:
    return build_plan(settings(**changes), window(), issues, sheet(existing))


def test_a_new_ticket_must_earn_its_row() -> None:
    """A ticket new to the sheet without comment content this week is not
    shown; a row already in the sheet is always refreshed, so nothing the
    user tracks silently stops updating."""
    plan = plan_for([SILENT, FIELD_TOUCH_ONLY])
    assert plan.rows == ()
    reasons = {item.key: item.reason for item in plan.skipped}
    assert reasons["GTM-455"] == "not in the sheet and no comment content this week"
    assert reasons["GTM-688"] == "not in the sheet and no comment content this week"
    added = plan_for([WORKED_ON])
    assert [row.key for row in added.rows] == ["GTM-1"] and added.new_keys == ("GTM-1",)
    refreshed = plan_for([FIELD_TOUCH_ONLY], existing={"GTM-688": "old text"})
    assert [row.key for row in refreshed.rows] == ["GTM-688"]
    assert refreshed.updated_keys == ("GTM-688",)
    assert refreshed.highlight_keys == () and refreshed.comment_operations == ()
    assert plan.issue_keys == ("GTM-455", "GTM-688")


def test_the_tint_and_the_red_text_point_at_the_same_rows() -> None:
    plan = plan_for([WORKED_ON, FIELD_TOUCH_ONLY], existing={"GTM-688": "x"})
    assert plan.highlight_keys == ("GTM-1",)
    assert [row.key for row in plan.rows] == ["GTM-1", "GTM-688"]
    assert plan.highlight_keys == tuple(op.key for op in plan.comment_operations)
    op = plan.comment_operations[0]
    assert op.markers == ("Completed",) and op.line_count == 1


def test_a_rerun_in_the_same_week_still_shows_the_mark() -> None:
    """Every run begins by retiring the previous run's marks. A second run
    in the same week has nothing to prepend, so it once cleared the first
    run's marks and put nothing back."""
    first = plan_for([WORKED_ON])
    already = first.comment_operations[0].text
    second = plan_for([WORKED_ON], existing={"GTM-1": already})
    assert second.comment_operations == (), "still nothing to write"
    assert second.highlight_keys == ("GTM-1",), "but the week is still marked"
    assert [remark.key for remark in second.remarks] == ["GTM-1"]
    assert [row.key for row in second.rows] == ["GTM-1"], "the row still refreshes"
    assert second.skipped[0].reason == "identical block already present (idempotent skip)"
    # Recolouring is by character offset, so a cell that no longer opens
    # with this week's block is left alone.
    third = plan_for([WORKED_ON], existing={"GTM-1": "a hand-written note\n" + already})
    assert third.remarks == () and third.comment_operations == ()


def test_the_header_is_the_comment_date_not_the_run_date() -> None:
    text = plan_for([WORKED_ON]).comment_operations[0].text
    assert text.startswith("7/29:"), text
    assert "8/1" not in text, "the run date leaked into the block"
    two_days = issue(
        "GTM-2",
        comment("2026-07-28T09:00:00.000+0800", "ongoing task:\n- fix rx power"),
        comment("2026-07-30T09:00:00.000+0800", "completed:\n- tx cal done"),
    )
    text = plan_for([two_days]).comment_operations[0].text
    assert text.index("7/30:") < text.index("7/28:") and text.splitlines()[0] == "7/30:"


def test_the_row_carries_the_sheets_own_sales_spelling_and_no_comments() -> None:
    legacy = sheet(headers=("Key", "Summary", "Company", "Status", "Assignee", "Salse", "Comments"))
    plan = build_plan(settings(), window(), [WORKED_ON], legacy)
    assert plan.sales_header == "Salse"
    assert plan.rows[0] == WeeklyRow(
        key="GTM-1", summary="[WNC] work", status="In Progress", assignee="Ming-Kai Shih"
    )
    assert "comments" not in WeeklyRow.model_fields
    unassigned = issue("GTM-3", comment("2026-07-29T09:00:00.000+0800", "todo:\n- x"))
    assert plan_for([unassigned.model_copy(update={"assignee": ""})]).rows[0].assignee == (
        "Unassigned"
    )


def test_the_preview_says_what_would_be_written_and_that_nothing_was() -> None:
    plan = plan_for([WORKED_ON, FIELD_TOUCH_ONLY], existing={"GTM-688": "x"})
    preview = plan.preview
    assert preview.startswith("# Planned Excel operations -- DRY RUN, nothing was written")
    assert "# week     : 2026_31W  (2026-07-27 .. 2026-08-02)" in preview
    assert f"# before   : {EMPTY_DIGEST}" in preview
    assert "upsert by Key  rows=2  (new=1, update=1)" in preview
    assert "   + GTM-1" in preview and "   ~ GTM-688" in preview
    assert "   GTM-1  markers=Completed  lines=1" in preview
    assert "        | 7/29:" in preview and "        | - tx cal" in preview
    assert "GTM-688: no marker-tagged comment content in window" in preview
    assert "rich-prepend G<row> color=#FF0000 dedupe=true  x1" in preview
    assert "fill A<row> = #FFF2CC  x1" in preview
    assert plan.summary() == (
        "2 row(s) (1 new, 1 updated); 1 comment block(s) to prepend, 0 to recolour, 1 skipped"
    )
    assert "CAPPED" not in preview and not plan.capped
    # A search the cap cut short is said to be one.
    short = build_plan(settings(), window(max_issues=1), [WORKED_ON], sheet(), capped=True)
    assert short.capped and "# CAPPED   : the search stopped at 1 issue(s)" in short.preview


def test_the_window_is_resolved_as_the_source_resolved_it() -> None:
    base = settings()
    named = resolve_window(
        base, week="2026_31W", since=None, until=None, max_issues=None, today=RUN_DATE
    )
    assert (named.since, named.until, named.stamp_date) == (START, END, RUN_DATE)
    assert named.comment_since == START and named.max_issues is None
    assert named.jql == (
        'project = GTM AND status in ("In Progress", "Ready for Launch", "To Do", "Pending") '
        'AND (updated >= "2026-07-27" AND updated < "2026-08-03") '
        "ORDER BY updated DESC, cf[10019] ASC"
    )
    # Run after the week ended: the stamp is the week's end, not today.
    later = resolve_window(
        base, week="2026_31W", since=None, until=None, max_issues=None, today=_dt.date(2026, 8, 20)
    )
    assert later.stamp_date == END
    # Today's week when none is named; an explicit window wins; either end
    # of a named week is overridable; the cap and the look-back apply.
    today = resolve_window(base, week=None, since=None, until=None, max_issues=None, today=RUN_DATE)
    assert today.week == "2026_31W" and (today.since, today.until) == (START, END)
    explicit = resolve_window(
        base,
        week=None,
        since=_dt.date(2026, 7, 1),
        until=_dt.date(2026, 7, 3),
        max_issues=5,
        today=RUN_DATE,
    )
    assert (explicit.since, explicit.until, explicit.max_issues) == (
        _dt.date(2026, 7, 1),
        _dt.date(2026, 7, 3),
        5,
    )
    shifted = resolve_window(
        base,
        week="2026_31W",
        since=_dt.date(2026, 7, 29),
        until=None,
        max_issues=None,
        today=RUN_DATE,
    )
    assert (shifted.since, shifted.until) == (_dt.date(2026, 7, 29), END)
    tuned = resolve_window(
        settings(
            lookback_days=3, max_issues=40, jql="project = X ORDER BY rank", week_style="iso-1"
        ),
        week="2026_30W",
        since=None,
        until=None,
        max_issues=None,
        today=RUN_DATE,
    )
    assert tuned.comment_since == START - _dt.timedelta(days=3)
    assert tuned.max_issues == 40 and tuned.since == START
    assert tuned.jql.startswith("project = X AND (updated >=") and tuned.jql.endswith(
        "ORDER BY rank"
    )


def test_a_request_is_parsed_from_the_words_after_the_command() -> None:
    parsed = WeeklyReportRequest(args="2026_31W since=2026-07-29 max=10")
    assert (parsed.week, parsed.since, parsed.max_issues) == ("2026_31W", _dt.date(2026, 7, 29), 10)
    assert WeeklyReportRequest(args="  ").week is None
    assert WeeklyReportRequest.model_validate({"week": "2026_31W"}).week == "2026_31W"
    # A field given directly wins over the text.
    assert WeeklyReportRequest(args="2026_31W", week="2026_30W").week == "2026_30W"
    with pytest.raises(ValidationError, match="sheet name"):
        WeeklyReportRequest(week="Sheet1")
    with pytest.raises(ValidationError, match="such as 2026_31W"):
        WeeklyReportRequest(args="everything")
    with pytest.raises(ValidationError, match="whole number"):
        WeeklyReportRequest(args="max=lots")
    with pytest.raises(ValidationError, match="no earlier"):
        WeeklyReportRequest(since=_dt.date(2026, 8, 2), until=_dt.date(2026, 7, 27))
    # A serialized request carries its defaults as None; the words still count.
    assert WeeklyReportRequest.model_validate({"args": "2026_31W", "week": None}).week == (
        "2026_31W"
    )
    with pytest.raises(ValidationError, match="names week once"):
        WeeklyReportRequest(args="2026_30W 2026_31W")
    with pytest.raises(ValidationError, match="names max_issues once"):
        WeeklyReportRequest(args="max=1 max_issues=2")
    # A window that cannot be, and a week the calendar has not got, are
    # refused by the resolver with a reason.
    with pytest.raises(ValueError, match="ends before it starts"):
        resolve_window(
            settings(),
            week="2026_31W",
            since=_dt.date(2026, 9, 1),
            until=None,
            max_issues=None,
            today=RUN_DATE,
        )
    with pytest.raises(ValueError, match="not a week the calendar has"):
        resolve_window(
            settings(), week="2025_53W", since=None, until=None, max_issues=None, today=RUN_DATE
        )


def test_the_settings_and_the_plan_are_closed_and_consistent() -> None:
    with pytest.raises(ValidationError, match="absolute"):
        settings(workbook_path="Report/SDE_Weekly_Report.xlsx")
    with pytest.raises(ValidationError):
        settings(key_highlight="yellow")
    with pytest.raises(ValidationError):
        settings(api_token="pasted")
    with pytest.raises(ValidationError, match="at least one marker"):
        settings(markers={})
    with pytest.raises(ValidationError):
        settings(week_suffix="wk")
    with pytest.raises(ValidationError):
        settings(page_size=50)  # the connection pages; the report has no page size
    assert settings(week_suffix="").week_suffix == ""
    assert settings(jql="project = X").base_jql() == "project = X"
    base = plan_for([WORKED_ON])

    def changed(**update: Any) -> WeeklyReportPlan:
        return WeeklyReportPlan.model_validate({**base.model_dump(), **update})

    with pytest.raises(ValidationError, match="new or updated"):
        changed(new_keys=())
    with pytest.raises(ValidationError, match="tinted once"):
        changed(highlight_keys=("GTM-1", "GTM-1"))
    with pytest.raises(ValidationError, match="sorted and unique"):
        changed(issue_keys=("b", "a"))
    with pytest.raises(ValidationError, match="planned row"):
        changed(comment_operations=({**base.comment_operations[0].model_dump(), "key": "X-1"},))
    assert WeeklyReportPlan.model_validate_json(base.model_dump_json()) == base
    with pytest.raises(ValidationError, match="source read"):
        sheet(source_sheet=None)
