"""The weekly mail uses Issue assignees and Project Production, not board text.

These shapes are based on the GitHub ProjectV2 query contract. No live
credential, network request, workbook or Outlook draft is used in these tests.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from capabilities.weekly_report import chart, effort, mail
from capabilities.weekly_report.contracts import ReportingWindow, WeeklyReportSettings
from capabilities.weekly_report.handlers import _as_item
from integrations.github_project import GitHubError, _item, _query_for

SETTINGS = WeeklyReportSettings(workbook_path=str(Path.cwd() / "weekly.xlsx"))


def project_node(*, production: str = "CMP180, CMX500") -> dict[str, object]:
    return {
        "id": "PVTI_42",
        "type": "ISSUE",
        "fieldValues": {
            "nodes": [
                {"text": "Project-only person", "field": {"name": "SDE Assignee"}},
                {"text": production, "field": {"name": "Production"}},
            ]
        },
        "content": {
            "number": 42,
            "title": "[GTM-42] CMX500 weekly work",
            "url": "https://github.com/team/repo/issues/42",
            "repository": {"nameWithOwner": "team/repo"},
            "assignees": {
                "pageInfo": {"hasNextPage": False},
                "nodes": [{"login": "alice"}, {"login": "bob"}],
            },
            "comments": {"totalCount": 0, "nodes": []},
        },
    }


def test_project_query_and_mapping_keep_issue_assignees_separate_from_project_text() -> None:
    assert "assignees(first: 100)" in _query_for("user")
    row = _item(project_node())
    assert row.issue_assignees == ("alice", "bob")
    assert row.fields["SDE Assignee"] == "Project-only person"
    report = _as_item(row, SETTINGS)
    assert report.assignee == "Project-only person"  # Workbook still owns this field.
    assert report.issue_assignees == ("alice", "bob")
    assert report.instrument == "CMP180, CMX500"
    assert effort.member_totals((report,)) == {"alice": 1, "bob": 1}
    assert effort.instrument_totals((report,)) == {"CMP180": 1, "CMX500": 1}
    assert effort.buckets((report,)) == {
        "alice": {"CMP180": ["GTM-42"], "CMX500": ["GTM-42"]},
        "bob": {"CMP180": ["GTM-42"], "CMX500": ["GTM-42"]},
    }


def test_empty_issue_assignees_and_production_are_unassigned_not_guessed() -> None:
    node = project_node(production="")
    content = node["content"]
    assert isinstance(content, dict)
    content["assignees"] = {"pageInfo": {"hasNextPage": False}, "nodes": []}
    report = _as_item(_item(node), SETTINGS)
    assert report.summary == "CMX500 weekly work"
    assert report.assignee == "Project-only person"
    assert report.issue_assignees == ()
    assert effort.member_totals((report,)) == {"Unassigned": 1}
    assert effort.instrument_totals((report,)) == {"Unassigned": 1}


def test_production_splits_commas_but_keeps_a_slash_inside_one_name() -> None:
    report = _as_item(
        _item(project_node(production="CMP180, CMX500，WMT2.0/NR")), SETTINGS
    )
    assert effort.instruments_for(report) == ["CMP180", "CMX500", "WMT2.0/NR"]


def test_assignee_connection_must_not_silently_truncate_member_counts() -> None:
    node = project_node()
    content = node["content"]
    assert isinstance(content, dict)
    content["assignees"] = {"pageInfo": {"hasNextPage": True}, "nodes": []}
    with pytest.raises(GitHubError, match="truncated"):
        _item(node)


def test_missing_assignee_connection_is_not_mistaken_for_unassigned() -> None:
    node = project_node()
    content = node["content"]
    assert isinstance(content, dict)
    del content["assignees"]
    with pytest.raises(GitHubError, match="connection is missing"):
        _item(node)


def test_mail_shows_every_production_name_and_explains_shared_issue_count() -> None:
    report = _as_item(_item(project_node()), SETTINGS)
    window = ReportingWindow(
        week="2026_40W", since=dt.date(2026, 9, 28), until=dt.date(2026, 10, 4),
        comment_since=dt.date(2026, 9, 28), stamp_date=dt.date(2026, 10, 4),
    )
    html = mail.build_html(window, (report,), chart_cid="chart")
    assert "2 member assignments from 1 ticket" in html
    assert "2 instrument-tickets from 1 ticket" in html
    assert "CMP180" in html and "CMX500" in html
    assert "Other (" not in html
    assert [name for name, _, _ in chart.slices_for(effort.instrument_totals((report,)))] == [
        "CMP180", "CMX500"
    ]
