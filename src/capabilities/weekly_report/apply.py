"""Writing a plan into the workbook, in the order the marks mean something.

The source's `apply_plan`, typed and behind a `WorkbookWriter`. The order is
not arbitrary and must not be rearranged:

* **Retire before you mark.** Both marks claim "this week". Red used to be
  demoted only on rows a run happened to touch and the tint was never cleared
  at all, so a ticket that stopped being updated kept both forever. The reset
  covers the whole sheet, which repaints rows this run would not otherwise
  touch: a red `Comments` cell or a tinted `Key` cell applied *by hand* loses
  its colour, though never its text.
* **Then recolour what is still true.** A second run in the same week has
  nothing to prepend, so without this it would clear the first run's marks
  and put nothing back.
* **Status fills are read, not cleared.** Unlike `Key`, the `Status` column
  carries the member's own colours; only cells holding exactly this job's
  pink are retired.

Nothing here knows about Excel. What it does know is that a plan was made
against a particular sheet, and it refuses to write it into a different one.
"""

from collections.abc import Sequence
from pathlib import Path
from typing import Literal

from capabilities.runtime import CapabilityRefused
from capabilities.weekly_report import rules
from capabilities.weekly_report.contracts import (
    FailedComment,
    WeeklyReportApplied,
    WeeklyReportPlan,
    WeeklyReportSettings,
    WeeklyRow,
)
from integrations import excel
from integrations.excel_writer import (
    Border,
    Fill,
    FontColour,
    FormatOperation,
    Hyperlink,
    TextRun,
    WorkbookWriteError,
    WorkbookWriter,
    column_letter,
    stage_workbook,
    unstage_workbook,
    workbook_is_open,
)

ApplyRefusalCode = Literal[
    "sheet_changed",
    "header_missing",
    "workbook_missing",
    "workbook_open",
]

#: How much of a block has to still sit at the top of a cell for a recolour
#: to be safe: recolouring is by character offset, so a cell somebody typed
#: over would get red in the wrong place.
RECOLOUR_HEAD = 24


class ApplyRefused(CapabilityRefused):
    """This plan was not written, and why. Nothing was changed, and the code
    is what the caller sees on the failed step."""

    def __init__(self, code: ApplyRefusalCode) -> None:
        super().__init__(code)


def scratch_digest(workbook: Path, sheet: str) -> tuple[str, bool]:
    """The scratch sheet's digest and whether it is there at all, read from
    the file's bytes so it means the same thing before and after a write."""

    def choose(names: tuple[str, ...]) -> str | None:
        return sheet if sheet in names else None

    _, source, headers, rows = excel.read_chosen_sheet(workbook, choose)
    if source is None:
        return excel.digest_rows((), ()), False
    return excel.digest_rows(headers, rows), True


def apply_plan(
    plan: WeeklyReportPlan,
    settings: WeeklyReportSettings,
    writer: WorkbookWriter,
    *,
    staging_root: Path,
) -> WeeklyReportApplied:
    """Execute a plan, or refuse it without touching anything.

    A run that does not finish leaves the real workbook exactly as it was and
    names the staged copy, which is a better outcome than a half-applied
    report in the file the team reads."""
    real = Path(settings.workbook_path)
    if not real.is_file():
        raise ApplyRefused("workbook_missing")
    if workbook_is_open(real) is not None:
        raise ApplyRefused("workbook_open")

    backup = writer.backup(real)
    staged: Path | None = None
    working = real
    if settings.local_staging:
        staged = stage_workbook(real, staging_root)
        working = staged

    # The sheet this plan was made against, before anything is opened.
    digest_before, present = scratch_digest(working, settings.temp_sheet)
    if plan.scratch_present and digest_before != plan.sheet_digest:
        raise ApplyRefused("sheet_changed")

    finished = False
    try:
        if not present:
            writer.ensure_sheet(working, settings.temp_sheet, seed=plan.seed_sheet)
        applied = _write(plan, settings, writer, working)
        finished = True
    finally:
        try:
            writer.close(working, save=finished)
        except WorkbookWriteError:
            # Releasing is best effort: a file the member cannot edit is a
            # worse outcome than the failure that caused it.
            pass
    if staged is not None:
        unstage_workbook(staged, real)
    digest_after, _ = scratch_digest(real, settings.temp_sheet)
    return applied.model_copy(
        update={
            "week": plan.window.week,
            "workbook": str(real),
            "sheet": settings.temp_sheet,
            "digest_before": digest_before,
            "digest_after": digest_after,
            "backup_path": str(backup) if backup is not None else None,
            "staged_path": str(staged) if staged is not None else None,
        }
    )


def _write(
    plan: WeeklyReportPlan,
    settings: WeeklyReportSettings,
    writer: WorkbookWriter,
    workbook: Path,
) -> WeeklyReportApplied:
    """Everything between opening the workbook and saving it."""
    headers = _headers(plan)
    sheet = settings.temp_sheet
    try:
        key_column = rules.column_for_header(headers, "Key")
        comments_column = rules.column_for_header(headers, "Comments")
    except KeyError:
        raise ApplyRefused("header_missing") from None
    try:
        status_column: str | None = rules.column_for_header(headers, "Status")
    except KeyError:
        # A sheet without a Status column is not an error: the run still has
        # a report to write, and only the pink has nowhere to go.
        status_column = None
    last_column = column_letter(len(headers))

    upsert = writer.upsert(
        workbook,
        sheet,
        headers=headers,
        key_header="Key",
        rows=[_record(row, plan.sales_header) for row in plan.rows],
    )
    placed = upsert.rows
    last_row = max(upsert.last_row, max(placed.values(), default=1))

    # 1. Retire last week's marks across the whole sheet.
    retired = 0
    if last_row >= 2:
        reset: list[FormatOperation] = [
            FontColour(
                range=f"{comments_column}2:{comments_column}{last_row}",
                colour=settings.comment_tail_color,
            ),
            Fill(range=f"{key_column}2:{key_column}{last_row}"),
        ]
        for cell, colour in _stale_fills(
            writer, workbook, sheet, status_column, last_row, settings.new_row_fill
        ).items():
            if colour.upper() == settings.new_row_fill.upper():
                reset.append(Fill(range=cell))
                retired += 1
        writer.format(workbook, sheet, reset)

    # 2. Tint what gained content this week, arrived this week, or already
    #    holds this week's content.
    tinted = [key for key in plan.highlight_keys if key in placed]
    if tinted:
        writer.format(
            workbook,
            sheet,
            [
                Fill(range=f"{key_column}{placed[key]}", colour=settings.key_highlight)
                for key in tinted
            ],
        )

    # 3. A row that was not on the sheet before reads as new without dates.
    new_rows = [key for key in plan.new_keys if key in placed]
    marks: list[FormatOperation] = []
    for key in new_rows:
        row = placed[key]
        if settings.new_row_border != "none":
            # A:last, not the Key..Sales span: Comments is part of the row a
            # person reads, and a border stopping short looks like a failure.
            marks.append(Border(range=f"A{row}:{last_column}{row}", style=settings.new_row_border))
        if status_column is not None:
            marks.append(Fill(range=f"{status_column}{row}", colour=settings.new_row_fill))
    if marks:
        writer.format(workbook, sheet, marks)

    # 4. Put the colour back on blocks the reset has just turned black.
    recoloured = 0
    for remark in plan.remarks:
        at = placed.get(remark.key)
        if at is not None and _recolour(
            writer, workbook, sheet, f"{comments_column}{at}", remark.text, settings
        ):
            recoloured += 1

    # 5. Every key cell links to its ticket, not only the new ones, so rows
    #    added by earlier runs heal instead of staying inconsistent.
    linked = 0
    if plan.browse_base:
        links: list[FormatOperation] = [
            Hyperlink(
                cell=f"{key_column}{placed[row.key]}",
                url=f"{plan.browse_base}/browse/{row.key}",
                text=row.key,
            )
            for row in plan.rows
            if row.key in placed
        ]
        if links:
            writer.format(workbook, sheet, links)
            linked = len(links)

    # 6. Prepend this week's block in red, with a black tail.
    prepended = 0
    failures: list[FailedComment] = []
    for operation in plan.comment_operations:
        at = placed.get(operation.key)
        if at is None:
            failures.append(FailedComment(key=operation.key, reason="no row was written for it"))
            continue
        cell = f"{comments_column}{at}"
        try:
            wrote = writer.rich_prepend(
                workbook,
                sheet,
                cell,
                text=operation.text,
                colour=settings.comment_color,
                tail_colour=settings.comment_tail_color,
            )
        except WorkbookWriteError as error:
            # One cell is not the week's report: record it and carry on.
            failures.append(FailedComment(key=operation.key, reason=error.code))
            continue
        if wrote:
            prepended += 1
        elif _recolour(writer, workbook, sheet, cell, operation.text, settings):
            # The writer found the block already at the top. The reset has
            # just turned it black, so putting the colour back is the whole
            # job here.
            recoloured += 1

    return WeeklyReportApplied(
        week=plan.window.week,
        workbook=str(workbook),
        sheet=sheet,
        digest_before="0" * 64,
        digest_after="0" * 64,
        inserted=upsert.inserted,
        updated=upsert.updated,
        highlighted=len(tinted),
        new_rows_marked=len(new_rows),
        recoloured=recoloured,
        prepended=prepended,
        linked=linked,
        retired_fills=retired,
        failures=tuple(failures),
    )


def _headers(plan: WeeklyReportPlan) -> list[str]:
    """The managed headers, in the workbook's own order, with whichever
    spelling of the Sales column the sheet uses."""
    return [
        plan.sales_header if header in rules.SALES_COLUMN_ALIASES else header
        for header in rules.WEEKLY_COLUMNS
    ]


def _record(row: WeeklyRow, sales_header: str) -> dict[str, str]:
    """A planned row as the managed columns the writer sets."""
    return {
        "Key": row.key,
        "Summary": row.summary,
        "Company": row.company,
        "Status": row.status,
        "Assignee": row.assignee,
        sales_header: row.sales,
    }


def _stale_fills(
    writer: WorkbookWriter,
    workbook: Path,
    sheet: str,
    column: str | None,
    last_row: int,
    colour: str,
) -> dict[str, str]:
    """The fills in the status column as they stand. A read that fails leaves
    the colours alone: a cosmetic reset must never cost the week's report,
    and a stale pink is a far smaller wrong than clearing a real one."""
    if column is None or last_row < 2:
        return {}
    try:
        return writer.fills(workbook, sheet, column, last_row)
    except WorkbookWriteError:
        return {}


def _recolour(
    writer: WorkbookWriter,
    workbook: Path,
    sheet: str,
    cell: str,
    block: str,
    settings: WeeklyReportSettings,
) -> bool:
    """Restore red on a block already sitting at the top of a cell, and only
    on a cell that really does still open with it."""
    head = block.rstrip("\n")
    try:
        current = writer.cell_text(workbook, sheet, cell)
        if not current.lstrip().startswith(head[:RECOLOUR_HEAD]):
            return False
        lead = len(current) - len(current.lstrip())
        cut = lead + len(head)
        writer.set_rich(
            workbook,
            sheet,
            cell,
            [
                TextRun(text=current[:cut], colour=settings.comment_color),
                TextRun(text=current[cut:], colour=settings.comment_tail_color),
            ],
        )
    except WorkbookWriteError:
        # A colour must not cost the run.
        return False
    return True


def evidence_lines(applied: WeeklyReportApplied, plan: WeeklyReportPlan) -> Sequence[str]:
    """What the parity gate reads: the key set, the counts, and the sheet's
    digest on both sides of the write."""
    return (
        f"week      : {applied.week}",
        f"keys      : {len(plan.issue_keys)} ({'capped' if plan.capped else 'complete'})",
        f"plan      : {plan.summary()}",
        f"applied   : {applied.summary()}",
        f"before    : {applied.digest_before}",
        f"after     : {applied.digest_after}",
        f"backup    : {applied.backup_path}",
    )
