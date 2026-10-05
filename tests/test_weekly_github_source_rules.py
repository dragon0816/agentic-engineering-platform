"""Workflow 11's board selection follows source `github_weekly_report.py`.

The source (rs_workflow_system host-bridge/jobs/github_weekly_report.py,
untracked after 896046e; sha256 recorded in docs/DECISIONS.md 2026-10-05)
reports only `[GTM-n]` issues that are not closed and that moved or were
commented inside the window; a comment edited inside the window counts at
its edit time; the migrated `## Weekly report comments` log in the body is a
fallback when no real marker comment is in the window; and `startTime` /
`endTime` select by moment, Taiwan time by default.
"""

from __future__ import annotations

import asyncio
import datetime as _dt
from pathlib import Path
from typing import Any

import pytest
from test_gateway import request

from capabilities.weekly_report.contracts import (
    ReportingWindow,
    WeeklyReportRequest,
    WeeklyReportSettings,
)
from capabilities.weekly_report.handlers import (
    ApplyHandler,
    ApplyInput,
    MailHandler,
    ProjectSearchHandler,
    ProjectSearchOutput,
)
from capabilities.weekly_report.plan import resolve_window
from integrations.github_project import ProjectComment, ProjectItem

TAIPEI = _dt.timezone(_dt.timedelta(hours=8))


def _settings(tmp_path: Path, **changes: Any) -> WeeklyReportSettings:
    return WeeklyReportSettings.model_validate(
        {"workbook_path": str(tmp_path / "w.xlsx"), **changes}
    )


def _item(number: int, title: str, *, status: str = "In Progress", updated: str = "",
          comments: tuple[ProjectComment, ...] = (), body: str = "") -> ProjectItem:
    return ProjectItem(
        item_id=f"PVTI_{number}", key=f"o/r#{number}", title=title, updated=updated,
        fields={"Status": status}, comments=comments, body=body, issue_assignees=("leo",),
    )


class Client:
    def __init__(self, rows: list[ProjectItem]) -> None:
        self.rows = rows

    def items(self) -> list[ProjectItem]:
        return self.rows


def _search(tmp_path: Path, rows: list[ProjectItem], **window: Any) -> ProjectSearchOutput:
    handler = ProjectSearchHandler(Client(rows), _settings(tmp_path))  # type: ignore[arg-type]
    inputs = {"since": _dt.date(2026, 9, 21), "until": _dt.date(2026, 9, 27), **window}
    result = asyncio.run(handler(request("search"), handler_input(inputs)))
    assert isinstance(result, ProjectSearchOutput)
    return result


def handler_input(values: dict[str, Any]) -> Any:
    from capabilities.weekly_report.handlers import ProjectSearchInput

    return ProjectSearchInput.model_validate(values)


IN_WEEK = "2026-09-23T03:00:00Z"
BEFORE = "2026-09-10T03:00:00Z"


def test_only_open_gtm_items_that_moved_in_the_window_are_reported(tmp_path: Path) -> None:
    found = _search(tmp_path, [
        _item(1, "[GTM-1] tracked", updated=IN_WEEK),
        _item(2, "board-only work", updated=IN_WEEK),               # no [GTM-n]
        _item(3, "[ABC-3] other tracker", updated=IN_WEEK),         # not GTM
        _item(4, "[GTM-4] finished", status="Done", updated=IN_WEEK),
        _item(5, "[GTM-5] closed", status="closed", updated=IN_WEEK),
        _item(6, "[GTM-6] quiet", updated=BEFORE),
        _item(7, "[GTM-7] no timestamp"),                           # source: not in window
    ])
    assert [item.key for item in found.items] == ["GTM-1"]
    assert found.items[0].summary == "tracked"


def test_a_comment_in_the_window_brings_an_item_in_and_edits_count_at_edit_time(
    tmp_path: Path,
) -> None:
    edited = ProjectComment(created=BEFORE, updated=IN_WEEK, body="[Completed]\n- edited")
    old = ProjectComment(created=BEFORE, updated=BEFORE, body="[Completed]\n- old")
    fresh = ProjectComment(created="2026-09-24T01:00:00Z", body="[On-going]\n- new")
    found = _search(tmp_path, [
        _item(8, "[GTM-8] commented", updated=BEFORE, comments=(old, edited, fresh)),
    ])
    (item,) = found.items
    assert [(c.created, c.body) for c in item.comments] == [
        (IN_WEEK, "[Completed]\n- edited"),
        ("2026-09-24T01:00:00Z", "[On-going]\n- new"),
    ]


def test_the_migrated_log_is_a_fallback_only_without_a_real_marker_comment(
    tmp_path: Path,
) -> None:
    body = ("Imported\n## Weekly report comments\n9/22:\n[Completed]\n- from excel\n"
            "9/10:\n[Completed]\n- too old\n")
    fallback = _search(tmp_path, [_item(9, "[GTM-9] migrated", updated=IN_WEEK, body=body)])
    (item,) = fallback.items
    assert [(c.created, c.body) for c in item.comments] == [
        ("2026-09-22T12:00:00+08:00", "[Completed]\n- from excel"),
    ]
    real = ProjectComment(created=IN_WEEK, body="[Completed]\n- real")
    preferred = _search(tmp_path, [
        _item(9, "[GTM-9] migrated", updated=IN_WEEK, body=body, comments=(real,)),
    ])
    assert [c.body for c in preferred.items[0].comments] == ["[Completed]\n- real"]


def test_a_precise_window_selects_by_moment_in_taiwan_time(tmp_path: Path) -> None:
    morning = ProjectComment(created="2026-09-22T00:30:00Z", body="[Completed]\n- 08:30")
    night = ProjectComment(created="2026-09-22T14:00:00Z", body="[Completed]\n- 22:00")
    request_ = WeeklyReportRequest.model_validate(
        {"start_time": "2026-09-22T08:00", "end_time": "2026-09-22T12:00"}
    )
    assert request_.start_time == _dt.datetime(2026, 9, 22, 8, 0, tzinfo=TAIPEI)
    found = _search(
        tmp_path, [_item(10, "[GTM-10] timed", updated=BEFORE, comments=(morning, night))],
        start_time=request_.start_time, end_time=request_.end_time,
    )
    assert [c.body for c in found.items[0].comments] == ["[Completed]\n- 08:30"]


def test_the_window_and_switches_resolve_as_the_source_does(tmp_path: Path) -> None:
    whole_day = WeeklyReportRequest.model_validate({"end_time": "2026-09-27"})
    assert whole_day.end_time == _dt.datetime(2026, 9, 27, 23, 59, 59, tzinfo=TAIPEI)
    window = resolve_window(
        _settings(tmp_path), week=None, since=None, until=None, max_issues=None,
        today=_dt.date(2026, 10, 5),
        start_time=_dt.datetime(2026, 9, 21, tzinfo=TAIPEI), end_time=whole_day.end_time,
        dry_run=True, draft_mail=False,
    )
    assert (window.since, window.until) == (_dt.date(2026, 9, 21), _dt.date(2026, 9, 27))
    assert window.dry_run is True and window.draft_mail is False
    with pytest.raises(ValueError, match="start_time"):
        WeeklyReportRequest.model_validate(
            {"start_time": "2026-09-28", "end_time": "2026-09-27"}
        )
    # Words after the command: the switches win over a form's defaults.
    words = WeeklyReportRequest.model_validate(
        {"args": "2026_39W dry-run no-mail", "dry_run": False, "draft_mail": True}
    )
    assert (words.week, words.dry_run, words.draft_mail) == ("2026_39W", True, False)


def test_a_dry_run_writes_nothing_and_drafts_nothing(tmp_path: Path) -> None:
    settings = _settings(tmp_path)

    def never() -> Any:
        raise AssertionError("a dry run must not open a writer")

    window = ReportingWindow(
        week="2026_39W", since=_dt.date(2026, 9, 21), until=_dt.date(2026, 9, 27),
        comment_since=_dt.date(2026, 9, 21), stamp_date=_dt.date(2026, 9, 27), dry_run=True,
    )
    from capabilities.weekly_report.contracts import WeeklyReportPlan

    plan = WeeklyReportPlan(window=window, sales_header="Sales", sheet_digest="a" * 64,
                            preview="nothing was written")
    applied = asyncio.run(ApplyHandler(settings, never, staging_root=tmp_path)(
        request("apply"), ApplyInput(plan=plan, skip=True)))
    assert applied.skipped is True and applied.inserted == 0  # type: ignore[attr-defined]
    mailer = MailHandler(settings, never, chart_root=tmp_path)
    from capabilities.weekly_report.handlers import MailInput

    drafted = asyncio.run(mailer(request("mail"), MailInput(window=window)))
    assert drafted.skipped is True  # type: ignore[attr-defined]
    no_mail = window.model_copy(update={"dry_run": False, "draft_mail": False})
    assert asyncio.run(mailer(request("mail"), MailInput(window=no_mail))).skipped  # type: ignore[attr-defined]
