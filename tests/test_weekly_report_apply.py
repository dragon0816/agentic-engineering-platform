"""Writing the weekly report's plan into the workbook.

Requirements: `docs/phases/PHASE_7_MIGRATION.md`, slice 3b. Every test drives
a recording writer, as the source's own tests drove a recording Bridge: there
is no Excel here and none in CI. The workbook on disk is real, built with
`openpyxl`, so the digests, the staging and the sheet-changed guard are
exercised against real bytes.
"""

import datetime as _dt
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from capabilities.weekly_report.apply import (
    ApplyRefused,
    apply_plan,
    evidence_lines,
    scratch_digest,
)
from capabilities.weekly_report.contracts import (
    ReportComment,
    ReportItem,
    SheetState,
    WeeklyReportPlan,
    WeeklyReportSettings,
)
from capabilities.weekly_report.plan import build_plan, resolve_window
from integrations import excel, excel_writer
from integrations.excel_writer import (
    Border,
    Fill,
    FontColour,
    TextRun,
    UpsertResult,
    WorkbookWriteError,
    column_letter,
    header_index,
    hyperlink_formula,
    owner_file,
    plain_key,
    require_com,
    stage_workbook,
    unstage_workbook,
    workbook_is_open,
)

openpyxl = pytest.importorskip("openpyxl")

RUN_DATE = _dt.date(2026, 8, 1)
HEADERS = ["Key", "Summary", "Company", "Status", "Assignee", "Sales", "Comments"]
OLD_BLOCK = "7/17:\n[Completed]\n- BT Tx BR LE are ready\n"
MINE = "#92D050"  # a colour the member put on a Status cell by hand


class RecordingWriter:
    """A `WorkbookWriter` that records what it was asked to do and answers
    from what the test set up. It changes no file, which is what lets a test
    assert that a failed run leaves the real workbook untouched."""

    def __init__(
        self,
        *,
        existing_rows: dict[str, int] | None = None,
        fills: dict[str, str] | None = None,
        cells: dict[str, str] | None = None,
        prepends: bool = True,
        fail_on: str | None = None,
        on_close: Any = None,
        sheets: tuple[str, ...] = ("2026_30W", "weekly report temp"),
        sheets_after: tuple[str, ...] | None = None,
    ) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.existing_rows = dict(existing_rows or {})
        self._fills = dict(fills or {})
        self._cells = dict(cells or {})
        self._prepends = prepends
        self._fail_on = fail_on
        self._on_close = on_close
        self._sheets = sheets
        self._sheets_after = sheets_after
        self._asked_sheets = 0
        self.closed_saving: bool | None = None

    def sheet_names(self, path: Path) -> tuple[str, ...]:
        # The second answer may differ, so a test can stand for a run that
        # lost a sheet on the way through.
        self._asked_sheets += 1
        if self._asked_sheets > 1 and self._sheets_after is not None:
            return self._sheets_after
        return self._sheets

    def _record(self, name: str, payload: Any = None) -> None:
        if self._fail_on == name:
            raise WorkbookWriteError("write_failed")
        self.calls.append((name, payload))

    @property
    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def operations(self) -> list[Any]:
        """Every format operation issued, in order, flattened."""
        out: list[Any] = []
        for name, payload in self.calls:
            if name == "format":
                out.extend(payload)
        return out

    # -- the protocol --------------------------------------------------

    def backup(self, path: Path) -> Path | None:
        self._record("backup", path)
        return path.with_name(path.stem + ".backup.xlsx")

    def ensure_sheet(self, path: Path, sheet: str, *, seed: str | None) -> None:
        self._record("ensure_sheet", (sheet, seed))

    def upsert(self, path: Path, sheet: str, *, headers: Any, key_header: str, rows: Any) -> Any:
        self._record("upsert", {"headers": list(headers), "rows": [dict(r) for r in rows]})
        placed = dict(self.existing_rows)
        next_row = max([*placed.values(), 1]) + 1
        inserted = updated = 0
        for record in rows:
            key = record[key_header]
            if key in placed:
                updated += 1
            else:
                placed[key] = next_row
                next_row += 1
                inserted += 1
        return UpsertResult(
            inserted=inserted,
            updated=updated,
            rows={record[key_header]: placed[record[key_header]] for record in rows},
            last_row=max([*placed.values(), 1]),
        )

    def fills(self, path: Path, sheet: str, column: str, last_row: int) -> dict[str, str]:
        self._record("fills", (column, last_row))
        return dict(self._fills)

    def format(self, path: Path, sheet: str, operations: Any) -> None:
        self._record("format", list(operations))

    def cell_text(self, path: Path, sheet: str, cell: str) -> str:
        self._record("cell_text", cell)
        return self._cells.get(cell, "")

    def rich_prepend(self, path: Path, sheet: str, cell: str, **changes: Any) -> bool:
        self._record("rich_prepend", {"cell": cell, **changes})
        return self._prepends

    def set_rich(self, path: Path, sheet: str, cell: str, runs: Any) -> None:
        self._record("set_rich", {"cell": cell, "runs": list(runs)})

    def close(self, path: Path, *, save: bool) -> None:
        self.closed_saving = save
        self._record("close", save)
        if self._on_close is not None:
            self._on_close()


def build_workbook(path: Path, *, scratch: bool = True, extra: list[str] | None = None) -> None:
    workbook = openpyxl.Workbook()
    week = workbook.active
    week.title = "2026_30W"
    week.append(HEADERS)
    week.append(["GTM-688", "[Acme] field edit", "Acme", "In Progress", "Ming", "Wendy", OLD_BLOCK])
    if scratch:
        temp = workbook.create_sheet("weekly report temp")
        temp.append(HEADERS)
        temp.append(
            ["GTM-688", "[Acme] field edit", "Acme", "In Progress", "Ming", "Wendy", OLD_BLOCK]
        )
        if extra:
            temp.append(extra)
    workbook.save(path)


def settings(workbook: Path, **changes: Any) -> WeeklyReportSettings:
    return WeeklyReportSettings.model_validate({"workbook_path": str(workbook), **changes})


def issue(key: str, body: str | None = None, *, summary: str = "[WNC] work") -> ReportItem:
    comments = (ReportComment(created="2026-07-29T09:00:00.000+0800", body=body),) if body else ()
    return ReportItem(
        key=key,
        summary=summary,
        status="In Progress",
        assignee="Ming-Kai Shih",
        company="Acme",
        sales="Wendy",
        comments=comments,
        browse_url=f"https://example-team.atlassian.net/browse/{key}",
    )


def sheet_state(workbook: Path, *, temp: str = "weekly report temp") -> SheetState:
    """The scratch sheet as it stands, read the way the plan step reads it."""

    def choose(names: tuple[str, ...]) -> str | None:
        return temp if temp in names else "2026_30W"

    names, source, headers, rows = excel.read_chosen_sheet(workbook, choose)
    lowered = [header.strip().lower() for header in headers]
    key_at, comments_at = lowered.index("key"), lowered.index("comments")
    existing = {row[key_at]: row[comments_at] for row in rows if row and row[key_at]}
    present = temp in names
    return SheetState(
        headers=tuple(headers),
        existing=existing,
        sheet_names=names,
        seed_sheet="2026_30W",
        scratch_present=present,
        source_sheet=source,
        digest=excel.digest_rows(headers, rows) if present else excel.digest_rows((), ()),
    )


def plan_for(workbook: Path, issues: list[ReportItem], **changes: Any) -> WeeklyReportPlan:
    config = settings(workbook, **changes)
    window = resolve_window(
        config, week="2026_31W", since=None, until=None, max_issues=None, today=RUN_DATE
    )
    return build_plan(config, window, issues, sheet_state(workbook))


# ---------------------------------------------------------------------------
# The writer's own rules
# ---------------------------------------------------------------------------


def test_the_writers_rules_are_the_sources() -> None:
    # Rule 4: a formula, never a COM Hyperlink object, and Excel's quoting.
    assert (
        hyperlink_formula("https://x/browse/G-1", "G-1")
        == '=HYPERLINK("https://x/browse/G-1","G-1")'
    )
    assert hyperlink_formula('a"b', 'c"d') == '=HYPERLINK("a""b","c""d")'
    # A key cell already holding our formula reads back as the bare key.
    assert plain_key('=HYPERLINK("https://x/browse/G-1","G-1")') == "G-1"
    assert plain_key("  G-2 ") == "G-2"
    assert plain_key("") == ""
    # Rule 3: case-insensitive headers.
    assert header_index(["Key", "Summary"], "key") == 1
    assert header_index([" SALES "], "Sales") == 1
    with pytest.raises(WorkbookWriteError, match="header_missing"):
        header_index(["Key"], "Comments")
    assert (column_letter(1), column_letter(7), column_letter(27)) == ("A", "G", "AA")


def test_a_workbook_somebody_has_open_is_refused_before_it_is_copied(tmp_path: Path) -> None:
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    assert workbook_is_open(workbook) is None
    lock = owner_file(workbook)
    lock.write_bytes(b"")
    assert workbook_is_open(workbook) == "owner_file"
    with pytest.raises(WorkbookWriteError, match="workbook_open"):
        stage_workbook(workbook, tmp_path / "state")
    assert not (tmp_path / "state").exists(), "nothing was copied"
    with pytest.raises(WorkbookWriteError, match="workbook_open"):
        unstage_workbook(workbook, workbook, retry_seconds=0.0)
    lock.unlink()
    staged = stage_workbook(workbook, tmp_path / "state")
    assert staged.read_bytes() == workbook.read_bytes()
    staged.write_bytes(b"changed")
    unstage_workbook(staged, workbook)
    assert workbook.read_bytes() == b"changed"


# ---------------------------------------------------------------------------
# The order the marks mean something in
# ---------------------------------------------------------------------------


def test_the_plan_is_written_in_the_sources_order(tmp_path: Path) -> None:
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    before = workbook.read_bytes()
    plan = plan_for(
        workbook,
        [issue("GTM-1", "completed:\n- tx cal"), issue("GTM-688", "ongoing task:\n- carry on")],
    )
    assert plan.new_keys == ("GTM-1",) and plan.updated_keys == ("GTM-688",)
    writer = RecordingWriter(
        existing_rows={"GTM-688": 2},
        fills={"D2": "#FFC7CE", "D3": MINE},  # last week's pink, and the member's own
    )
    applied = apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")

    assert writer.names == [
        "backup",
        "upsert",
        "fills",
        "format",  # the reset
        "format",  # the tint
        "format",  # the new row's border and pink
        "format",  # the links
        "rich_prepend",
        "rich_prepend",
        "close",
    ]
    reset = writer.calls[3][1]
    # The reset covers the whole sheet, not only the rows this run touched.
    assert FontColour(range="G2:G3", colour="#000000") in reset
    assert Fill(range="A2:A3") in reset
    # Only this job's pink is retired; the member's own colour is left alone.
    assert Fill(range="D2") in reset and Fill(range="D3") not in reset
    assert applied.retired_fills == 1
    # The tint names exactly the rows that gained content this week.
    assert writer.calls[4][1] == [
        Fill(range="A3", colour="#FFF2CC"),
        Fill(range="A2", colour="#FFF2CC"),
    ]
    # A new row reads as new: the border reaches the Comments column.
    marks = writer.calls[5][1]
    assert Border(range="A3:G3", style="thin") in marks
    assert Fill(range="D3", colour="#FFC7CE") in marks
    # Every key links, not only the new ones, so old rows heal.
    links = writer.calls[6][1]
    assert [op.cell for op in links] == ["A3", "A2"]
    assert links[0].formula == (
        '=HYPERLINK("https://example-team.atlassian.net/browse/GTM-1","GTM-1")'
    )
    # The block goes in red with a black tail.
    prepend = writer.calls[7][1]
    assert prepend["cell"] == "G3"
    assert prepend["colour"] == "#FF0000" and prepend["tail_colour"] == "#000000"
    assert prepend["text"].startswith("7/29:")
    assert writer.closed_saving is True

    assert (applied.inserted, applied.updated) == (1, 1)
    assert (applied.highlighted, applied.new_rows_marked, applied.prepended) == (2, 1, 2)
    assert applied.linked == 2 and applied.failures == ()
    assert applied.week == "2026_31W" and applied.sheet == "weekly report temp"
    assert applied.backup_path is not None and applied.staged_path is not None
    # The recording writer changed nothing, so both digests are the sheet as
    # it stood -- and the plan was made against exactly that.
    assert applied.digest_before == plan.sheet_digest == applied.digest_after
    assert workbook.read_bytes() == before
    lines = evidence_lines(applied, plan)
    assert any("before    :" in line for line in lines)
    assert any("2 row(s) (1 new, 1 updated)" in line for line in lines)


def test_a_second_run_in_the_same_week_recolours_instead_of_prepending(tmp_path: Path) -> None:
    """The reset has just turned the block black; there is nothing to
    prepend, so putting the colour back is the whole job."""
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    first = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    block = first.comment_operations[0].text
    # The sheet now holds the block, so the plan remarks instead of writing.
    build_workbook(
        workbook, extra=["GTM-1", "[WNC] work", "Acme", "In Progress", "Ming", "Wendy", block]
    )
    second = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    assert second.comment_operations == () and [r.key for r in second.remarks] == ["GTM-1"]
    writer = RecordingWriter(existing_rows={"GTM-688": 2, "GTM-1": 3}, cells={"G3": block})
    applied = apply_plan(second, settings(workbook), writer, staging_root=tmp_path / "state")
    assert "rich_prepend" not in writer.names
    rich = [payload for name, payload in writer.calls if name == "set_rich"]
    assert len(rich) == 1 and rich[0]["cell"] == "G3"
    # The block is red and everything after it, the newline included, black.
    assert rich[0]["runs"] == [
        TextRun(text=block.rstrip("\n"), colour="#FF0000"),
        TextRun(text="\n", colour="#000000"),
    ]
    assert applied.recoloured == 1 and applied.prepended == 0
    # The week is still marked even though nothing was written.
    assert applied.highlighted == 1


def test_a_cell_that_moved_on_is_not_recoloured(tmp_path: Path) -> None:
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    # The writer says the block is already there, but the cell now opens with
    # somebody's own note: recolouring by offset would put red in the wrong
    # place, so it is left alone.
    writer = RecordingWriter(
        existing_rows={"GTM-688": 2},
        prepends=False,
        cells={"G3": "a hand-written note\n" + plan.comment_operations[0].text},
    )
    applied = apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert applied.prepended == 0 and applied.recoloured == 0
    assert "set_rich" not in writer.names


def test_a_comment_cell_that_cannot_be_written_does_not_fail_the_week(tmp_path: Path) -> None:
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    writer = RecordingWriter(existing_rows={"GTM-688": 2}, fail_on="rich_prepend")
    applied = apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert applied.prepended == 0
    assert [(f.key, f.reason) for f in applied.failures] == [("GTM-1", "write_failed")]
    # The rest of the run stands: the row was written and the marks made.
    assert applied.inserted == 1 and applied.highlighted == 1
    assert writer.closed_saving is True


# ---------------------------------------------------------------------------
# Refusals
# ---------------------------------------------------------------------------


def test_a_sheet_that_changed_since_planning_is_refused(tmp_path: Path) -> None:
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    before = workbook.read_bytes()
    # Somebody adds a row between planning and writing.
    build_workbook(workbook, extra=["GTM-9", "added by hand", "", "", "", "", ""])
    writer = RecordingWriter(existing_rows={"GTM-688": 2})
    with pytest.raises(ApplyRefused) as refused:
        apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert refused.value.code == "sheet_changed"
    assert writer.calls == [], "nothing was written, and nothing backed up"
    assert not (tmp_path / "state").exists(), "nothing was copied"
    # The plan still fits the sheet it was made against.
    restored = tmp_path / "restored.xlsx"
    restored.write_bytes(before)
    assert scratch_digest(restored, "weekly report temp")[0] == plan.sheet_digest


def test_a_missing_or_open_workbook_is_refused_before_anything(tmp_path: Path) -> None:
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    writer = RecordingWriter()
    gone = settings(tmp_path / "nowhere.xlsx")
    with pytest.raises(ApplyRefused) as missing:
        apply_plan(plan, gone, writer, staging_root=tmp_path / "state")
    assert missing.value.code == "workbook_missing" and writer.calls == []
    owner_file(workbook).write_bytes(b"")
    with pytest.raises(ApplyRefused) as opened:
        apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert opened.value.code == "workbook_open" and writer.calls == []


def test_a_run_that_fails_leaves_the_real_workbook_untouched(tmp_path: Path) -> None:
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    before = workbook.read_bytes()
    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    writer = RecordingWriter(existing_rows={"GTM-688": 2}, fail_on="format")
    with pytest.raises(WorkbookWriteError, match="write_failed"):
        apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    # The workbook is closed without saving, the real file is as it was, and
    # the staged copy is still there to look at.
    assert writer.closed_saving is False
    assert workbook.read_bytes() == before
    staged = tmp_path / "state" / "weekly-report-staging" / workbook.name
    assert staged.is_file() and staged.read_bytes() == before


def test_a_scratch_sheet_that_is_not_there_yet_is_created_from_the_seed(tmp_path: Path) -> None:
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook, scratch=False)
    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    assert not plan.scratch_present and plan.seed_sheet == "2026_30W"
    writer = RecordingWriter()
    applied = apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert writer.calls[1] == ("ensure_sheet", ("weekly report temp", "2026_30W"))
    # Nothing to compare against, so the digest of nothing stands.
    assert applied.digest_before == excel.digest_rows((), ())


def test_staging_can_be_turned_off(tmp_path: Path) -> None:
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")], local_staging=False)
    writer = RecordingWriter(existing_rows={"GTM-688": 2})
    applied = apply_plan(
        plan, settings(workbook, local_staging=False), writer, staging_root=tmp_path / "state"
    )
    assert applied.staged_path is None
    assert not (tmp_path / "state").exists()
    assert writer.calls[1][1]["rows"][0]["Key"] == "GTM-1"


def test_the_comments_column_is_never_a_managed_header(tmp_path: Path) -> None:
    """Rule 2, and the whole reason the hand-kept log survives a run.

    A writer sets every managed header from the record it is given. The
    record has no `Comments`, so naming that column as managed would set it
    to the empty string on every planned row -- the exact loss the rule
    exists to prevent. It is prevented by never naming the column."""
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    writer = RecordingWriter(existing_rows={"GTM-688": 2})
    apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    written = writer.calls[1][1]
    assert written["headers"] == ["Key", "Summary", "Company", "Status", "Assignee", "Sales"]
    assert "Comments" not in written["headers"]
    for row in written["rows"]:
        assert set(row) == set(written["headers"])
    # Every managed header has a value; nothing is written as a blank by
    # default, which is how the loss happened.
    assert all(name in written["rows"][0] for name in written["headers"])


def test_the_columns_are_the_sheets_own_not_the_contracts(tmp_path: Path) -> None:
    """A member's sheet with an extra column is still written in the right
    places, and in the same places the preview named."""
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    layout = ["Key", "Summary", "Company", "Status", "Assignee", "Salse", "Notes", "Comments"]
    book = openpyxl.Workbook()
    week = book.active
    week.title = "2026_30W"
    week.append(layout)
    temp = book.create_sheet("weekly report temp")
    temp.append(layout)
    temp.append(["GTM-688", "edit", "Acme", "In Progress", "Ming", "Wendy", "mine", OLD_BLOCK])
    book.save(workbook)

    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    assert plan.sheet_headers == tuple(layout)
    assert plan.sales_header == "Salse", "the sheet's own spelling"
    writer = RecordingWriter(existing_rows={"GTM-688": 2})
    apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    # Comments is H here, not G, and the row's border reaches it.
    reset = writer.calls[3][1]
    assert FontColour(range="H2:H3", colour="#000000") in reset
    assert Fill(range="A2:A3") in reset
    marks = writer.calls[5][1]
    assert Border(range="A3:H3", style="thin") in marks
    prepend = [payload for name, payload in writer.calls if name == "rich_prepend"]
    assert prepend[0]["cell"] == "H3"
    # The member's own spelling of the Sales column is what gets written.
    assert "Salse" in writer.calls[1][1]["headers"]
    assert "Notes" not in writer.calls[1][1]["headers"], "an unmanaged column is left alone"


def test_a_plan_made_without_a_scratch_sheet_is_not_written_into_a_new_one(
    tmp_path: Path,
) -> None:
    """Presence counts as much as content: a sheet somebody made in between
    is not the sheet this plan was made against."""
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook, scratch=False)
    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    assert not plan.scratch_present
    build_workbook(workbook, scratch=True)
    writer = RecordingWriter()
    with pytest.raises(ApplyRefused) as refused:
        apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert refused.value.code == "sheet_changed"
    assert writer.calls == [], "not even a backup"


def test_a_write_back_that_fails_is_not_reported_as_nothing_happened(tmp_path: Path) -> None:
    """The report was written and saved; only the copy back failed, and the
    finished workbook is the staged one. Saying `workbook_open` here would
    read as "nothing happened" and the next run would stage over it."""
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    plan = plan_for(workbook, [issue("GTM-1", "completed:\n- tx cal")])
    writer = RecordingWriter(
        existing_rows={"GTM-688": 2},
        on_close=lambda: owner_file(workbook).write_bytes(b""),
    )
    with pytest.raises(ApplyRefused) as refused:
        apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert refused.value.code == "write_back_failed"
    assert writer.closed_saving is True, "the report was saved"
    staged = tmp_path / "state" / "weekly-report-staging" / workbook.name
    assert staged.is_file()


def fake_bridge(monkeypatch: pytest.MonkeyPatch, *, excel_registered: bool) -> None:
    """Stand in for the bridge this machine does not have.

    Only the bridge. Whether Excel is registered is a question about the
    machine, and it is answered by `progid_is_registered`, which reads the
    real registry and has its own test against it: faking that question is
    what let a made-up API through on 2026-09-24.
    """
    client = types.ModuleType("win32com.client")
    win32com = types.ModuleType("win32com")
    win32com.client = client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    monkeypatch.setattr(excel_writer, "progid_is_registered", lambda _p: excel_registered)


def test_a_machine_without_excel_is_not_a_machine_that_can_write(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The bundle carries the bridge on every machine, so an importable
    `win32com` says nothing about Excel. Answering `can write it` on the
    strength of the import would promise a write that fails at the first
    `DispatchEx`."""
    fake_bridge(monkeypatch, excel_registered=False)
    with pytest.raises(WorkbookWriteError) as refused:
        require_com()
    assert refused.value.code == "excel_missing"


def test_a_machine_with_excel_can_write(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_bridge(monkeypatch, excel_registered=True)
    require_com()


def test_a_missing_bridge_is_a_different_absence_from_a_missing_excel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Different people fix them: one is this installation, the other is the
    machine. This test machine has no bridge at all."""
    monkeypatch.setitem(sys.modules, "win32com.client", None)
    with pytest.raises(WorkbookWriteError) as refused:
        require_com()
    assert refused.value.code == "library_missing"


def test_a_report_that_could_not_be_saved_is_not_reported_as_written(tmp_path: Path) -> None:
    """The write succeeded in Excel and the save did not, so the report is
    not in the file. Copying the staged workbook back would put the old
    content over the real one and call the run a success."""
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    plan = plan_for(workbook, [issue("GTM-1", "completed:" + chr(10) + "- tx cal")])

    def refuse_to_save() -> None:
        raise WorkbookWriteError("save_failed")

    writer = RecordingWriter(existing_rows={"GTM-688": 2}, on_close=refuse_to_save)
    before = workbook.read_bytes()
    with pytest.raises(WorkbookWriteError) as refused:
        apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert refused.value.code == "save_failed"
    assert workbook.read_bytes() == before, "the real workbook was not touched"
    staged = tmp_path / "state" / "weekly-report-staging" / workbook.name
    assert staged.is_file(), "the staged copy remains, but it is the one from before the run"


def test_a_handle_that_would_not_release_does_not_fail_a_finished_report(
    tmp_path: Path,
) -> None:
    """The report is saved and the only thing that failed is letting go of
    the file. Failing the run here would strand a finished report in staging
    and tell the member nothing was written."""
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    plan = plan_for(workbook, [issue("GTM-1", "completed:" + chr(10) + "- tx cal")])

    def stuck_handle() -> None:
        raise WorkbookWriteError("write_failed")

    writer = RecordingWriter(existing_rows={"GTM-688": 2}, on_close=stuck_handle)
    applied = apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert applied.digest_after, "the run finished and its evidence is complete"


def test_a_run_that_would_lose_a_sheet_is_refused(tmp_path: Path) -> None:
    """The first real run of this writer lost a week's own sheet from the
    team's workbook, and nothing noticed until somebody looked at the tabs.
    Every sheet but the scratch one has to come through untouched, and that
    is now checked rather than trusted."""
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook)
    plan = plan_for(workbook, [issue("GTM-1", "completed:" + chr(10) + "- tx cal")])
    writer = RecordingWriter(
        existing_rows={"GTM-688": 2},
        sheets=("2026_30W", "weekly report temp"),
        sheets_after=("weekly report temp",),
    )
    before = workbook.read_bytes()
    with pytest.raises(ApplyRefused) as refused:
        apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert refused.value.code == "sheets_lost"
    assert writer.closed_saving is False, "a workbook missing a sheet is not saved"
    assert workbook.read_bytes() == before, "and the real one is untouched"


def test_the_scratch_sheet_may_appear_and_nothing_else_may(tmp_path: Path) -> None:
    """A run that creates the scratch sheet is the ordinary case."""
    workbook = tmp_path / "SDE_Weekly_Report.xlsx"
    build_workbook(workbook, scratch=False)
    plan = plan_for(workbook, [issue("GTM-1", "completed:" + chr(10) + "- tx cal")])
    writer = RecordingWriter(sheets=("2026_30W",), sheets_after=("2026_30W", "weekly report temp"))
    applied = apply_plan(plan, settings(workbook), writer, staging_root=tmp_path / "state")
    assert applied.digest_after

    # A sheet nobody asked for is as wrong as a sheet that went.
    stranger = RecordingWriter(
        sheets=("2026_30W",), sheets_after=("2026_30W", "weekly report temp", "Sheet1")
    )
    with pytest.raises(ApplyRefused) as refused:
        apply_plan(plan, settings(workbook), stranger, staging_root=tmp_path / "state")
    assert refused.value.code == "sheets_lost"
