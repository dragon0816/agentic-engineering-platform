"""The offline preview of Workflow 11 and the week's own sheet.

Synthetic data only: the fixture board and workbook in
`capabilities.weekly_report.preview` are invented, no credential or network
is used, and nothing outside `tmp_path` is written.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from test_gateway import request

from capabilities.weekly_report import chart
from capabilities.weekly_report.contracts import SheetState, WeeklyReportSettings
from capabilities.weekly_report.handlers import ReadScratchSheetHandler, ReadScratchSheetInput
from capabilities.weekly_report.preview import (
    FIXTURE_WORKBOOK,
    PREVIEW_WORKBOOK,
    FixtureBoard,
    main,
    run_preview,
    write_fixture_workbook,
)
from capabilities.weekly_report.rules import WEEKLY_COLUMNS

openpyxl = pytest.importorskip("openpyxl")
HAS_MATPLOTLIB = importlib.util.find_spec("matplotlib") is not None


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fixture_preview_writes_only_its_folder_and_keys_rows_by_github_issue(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out = tmp_path / "preview"
    assert (
        main(["--week", "2026_43W", "--out", str(out), "--fixture", "--today", "2026-10-26"]) == 0
    )
    expected = {"plan.json", "email.html", FIXTURE_WORKBOOK, PREVIEW_WORKBOOK}
    if HAS_MATPLOTLIB:
        expected.add("effort-chart.png")
    assert {path.name for path in tmp_path.rglob("*") if path.is_file()} == expected
    assert "week 2026_43W" in capsys.readouterr().out

    record = json.loads((out / "plan.json").read_text(encoding="utf-8"))
    assert record["sheet"] == "2026_43W"
    assert record["window"] == {
        "since": "2026-10-19",
        "until": "2026-10-25",
        "start_time": None,
        "end_time": None,
        "days_in": "Asia/Taipei (UTC+8)",
    }
    tickets = {ticket["key"]: ticket for ticket in record["tickets"]}
    # Closed (#105) and quiet (#106) Issues leave; an Issue edited but not
    # commented (#104) is in scope and not counted.
    assert set(tickets) == {"#101", "#102", "#103", "#104"}
    assert record["counts"]["tickets_in_scope"] == 4
    assert record["counts"]["commented_in_window"] == 3
    assert record["counts"]["new_rows"] == 3 and record["counts"]["linked_keys"] == 3
    # The GitHub-only Issue is included; the migrated one keeps its old id
    # only as metadata.
    assert tickets["#102"]["jira_key"] is None and tickets["#102"]["sheet"] == "new row"
    assert tickets["#101"]["jira_key"] == "GTM-901"
    assert tickets["#101"]["summary"] == "Example migrated ticket"
    assert tickets["#101"]["url"].endswith("/issues/101")
    # The SDE Assignee fallback, with its source named.
    assert tickets["#103"]["assignee"] == "Casey Lin"
    assert tickets["#103"]["assignee_source"] == "project_field"
    # Monday 07:00 Taipei is Sunday in UTC and still this week.
    assert tickets["#103"]["comment_block"].startswith("10/19:")
    assert tickets["#102"]["instruments"] == ["CMX500", "CMP180"]
    assert tickets["#104"]["commented_in_window"] is False
    assert tickets["#104"]["sheet"] == "not written"

    # The workbook copy: the week's own sheet, appended, Key cells linked.
    book = openpyxl.load_workbook(out / PREVIEW_WORKBOOK)
    assert book.sheetnames == ["Tasks Summary", "2026_41W", "2026_42W", "2026_43W"]
    week = book["2026_43W"]
    assert [cell.value for cell in week[1]] == list(WEEKLY_COLUMNS)
    keys = [week.cell(row, 1).value for row in range(2, week.max_row + 1)]
    assert keys == ["#101", "#102", "#103"]
    for row in range(2, 5):
        cell = week.cell(row, 1)
        assert cell.hyperlink is not None
        assert cell.hyperlink.target == (
            f"https://github.com/example-org/example-board/issues/{cell.value[1:]}"
        )
        assert cell.border.left.style == "thin"
    assert "example step" in str(week["G2"].value)
    # The older weeks are untouched, their Jira-era keys included.
    assert book["2026_41W"]["A2"].value == "GTM-900"
    assert book["2026_42W"]["A2"].value == "#101"

    html = (out / "email.html").read_text(encoding="utf-8")
    assert "SDE Weekly Report &mdash; 2026_43W" in html
    assert "2026-10-19 &ndash; 2026-10-25" in html
    assert "本週有留言的 <b>3</b> / 4 張" in html
    assert "GitHub Project example-board" in html
    assert "Effort below is a <b>ticket count</b>, not hours" in html
    assert "Tickets per team member" in html
    assert "4 instrument-tickets from 3 tickets" in html
    assert "cid:" not in html
    if HAS_MATPLOTLIB:
        assert "src='effort-chart.png'" in html


def test_the_configured_workbook_is_only_read(tmp_path: Path) -> None:
    configured = tmp_path / "configured" / "SDE_Weekly_Report.xlsx"
    configured.parent.mkdir()
    write_fixture_workbook(configured)
    before = _digest(configured)
    out = tmp_path / "preview"
    record = run_preview(
        WeeklyReportSettings(workbook_path=str(configured), project="example-board"),
        FixtureBoard(),
        out,
        week="2026_43W",
        today=dt.date(2026, 10, 26),
    )
    assert _digest(configured) == before
    assert sorted(path.name for path in configured.parent.iterdir()) == [configured.name]
    assert record["configured_workbook"] == str(configured)
    assert "2026_43W" not in openpyxl.load_workbook(configured).sheetnames
    assert "2026_43W" in openpyxl.load_workbook(out / PREVIEW_WORKBOOK).sheetnames


def _book(path: Path, sheets: dict[str, list[list[str]]]) -> None:
    book = openpyxl.Workbook()
    book.remove(book.active)
    for name, rows in sheets.items():
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append(row)
    book.save(path)


def _read(settings: WeeklyReportSettings, week: str) -> SheetState:
    state = asyncio.run(
        ReadScratchSheetHandler(settings)(request("read"), ReadScratchSheetInput(week=week))
    )
    assert isinstance(state, SheetState)
    return state


def test_the_weeks_own_sheet_is_the_target_and_is_never_seeded(tmp_path: Path) -> None:
    workbook = tmp_path / "book.xlsx"
    header = list(WEEKLY_COLUMNS)
    _book(
        workbook,
        {
            "2026_42W": [header, ["GTM-1", "old", "", "", "", "", "7/1:\n- x"]],
            "weekly report temp": [header, ["GTM-2", "scratch", "", "", "", "", ""]],
        },
    )
    settings = WeeklyReportSettings(workbook_path=str(workbook))
    absent = _read(settings, "2026_43W")
    assert absent.target_sheet == "2026_43W"
    assert absent.scratch_present is False and absent.seed_sheet is None
    assert absent.existing == {} and absent.headers == WEEKLY_COLUMNS

    _book(
        workbook,
        {
            "2026_42W": [header],
            "2026_43W": [header, ["#7", "this week", "", "", "", "", "10/20:\n- y"]],
        },
    )
    present = _read(settings, "2026_43W")
    assert present.target_sheet == "2026_43W" and present.scratch_present is True
    assert present.existing == {"#7": "10/20:\n- y"}

    # The older scratch sheet is still a way back.
    temp = _read(WeeklyReportSettings(workbook_path=str(workbook), sheet_target="temp"), "2026_43W")
    assert temp.target_sheet == "weekly report temp" and temp.seed_sheet == "2026_42W"


def test_the_pie_title_names_instrument_tickets_and_tickets() -> None:
    assert chart.instrument_title(23, 19) == (
        "Tickets by instrument  (23 instrument-tickets from 19 tickets)"
    )
    assert chart.instrument_title(1, 1).endswith("(1 instrument-tickets from 1 ticket)")
