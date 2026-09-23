"""Writing a workbook, and the one adapter that does it through Excel.

The protocol is the vocabulary the pinned Host Bridge's Excel service
exposed, typed (`docs/PHASE_7_MIGRATION.md`, "Workflow 11"). The executor in
`capabilities.weekly_report.apply` speaks only this; `ExcelComWriter` is the
one thing that knows about Excel, so the owner's choice of COM is reversible
by writing another adapter and nothing else.

Rules carried from the source's `_excel_upsert`, each of which exists because
of a real bug in the PowerShell scripts before it:

1. The last data row comes from the **used range**, which counts hidden rows.
   `End(xlUp)` skipped hidden (closed) rows, so most keys went unmapped and
   rows were re-appended on top of existing ones.
2. Only **managed** headers are ever written. Every other column is left
   alone; that is how the hand-kept `Comments` column survives every run.
3. Header matching is **case-insensitive**, as the PowerShell hashtable was.
   Making it case-sensitive would silently duplicate columns.
4. A key cell is an `=HYPERLINK()` **formula**, never a COM Hyperlink object:
   those leak references and keep `EXCEL.EXE` alive after the run.

Staging is the source's measured behaviour: a workbook driven in its OneDrive
folder took 1001s against 137s for a local copy, because every write saves
the whole file and a sync client watching the folder gets one upload per
write. Staging removes the watcher, not the saves.
"""

import os
import shutil
import time
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Annotated, Any, Literal, Protocol

from pydantic import Field, StringConstraints

from common.base import Contract, Text

Colour = Annotated[str, StringConstraints(pattern=r"^#[0-9A-Fa-f]{6}$")]
BorderStyle = Literal["thin", "medium", "none"]

WorkbookWriteErrorCode = Literal[
    "library_missing",
    "excel_missing",
    "save_failed",
    "workbook_missing",
    "workbook_open",
    "workbook_unwritable",
    "sheet_missing",
    "header_missing",
    "write_failed",
]

#: How long to keep retrying the copy back onto the real workbook. A sync
#: client holds a brief lock of its own while it uploads, and losing a run's
#: work to a lock that clears in two seconds would be absurd.
UNSTAGE_RETRY_SECONDS = 30.0
#: The same, for the save itself. Past this the run's work is gone, because
#: the workbook is released either way, so it is worth waiting the same.
SAVE_RETRY_SECONDS = 30.0
#: xlEdgeLeft, xlEdgeTop, xlEdgeBottom, xlEdgeRight and xlInsideVertical.
_EDGE_BORDERS = (7, 8, 9, 10)
_INSIDE_VERTICAL = 11
STAGING_DIR = "weekly-report-staging"


class WorkbookWriteError(Exception):
    """The code is the whole message: no path, sheet, cell or value is
    echoed, because any of them may carry the team's own data."""

    def __init__(self, code: WorkbookWriteErrorCode) -> None:
        self.code: WorkbookWriteErrorCode = code
        super().__init__(code)


# ---------------------------------------------------------------------------
# What a write is made of
# ---------------------------------------------------------------------------


class Fill(Contract):
    """A cell range's background. `colour` absent clears it, which is not the
    same as white: Excel reports an unfilled cell as white and only
    `ColorIndex = xlNone` means no fill."""

    kind: Literal["fill"] = "fill"
    range: Text
    colour: Colour | None = None


class FontColour(Contract):
    kind: Literal["font"] = "font"
    range: Text
    colour: Colour


class Border(Contract):
    kind: Literal["border"] = "border"
    range: Text
    style: BorderStyle


class Hyperlink(Contract):
    """A key cell as a formula. `formula` is what a writer sets; `url` and
    `text` are kept so evidence reads as something other than a formula."""

    kind: Literal["hyperlink"] = "hyperlink"
    cell: Text
    url: Text
    text: Text

    @property
    def formula(self) -> str:
        return hyperlink_formula(self.url, self.text)


FormatOperation = Fill | FontColour | Border | Hyperlink


class TextRun(Contract):
    """One run of a rich cell: some text in one colour."""

    text: str
    colour: Colour


class UpsertResult(Contract):
    """What an upsert did, and where each key landed. `rows` maps a key to
    its 1-based row so everything after this can address cells by key."""

    inserted: int = Field(ge=0, strict=True)
    updated: int = Field(ge=0, strict=True)
    rows: dict[str, int] = {}
    last_row: int = Field(ge=0, strict=True)


class WorkbookWriter(Protocol):
    """Everything the weekly report's executor needs of a workbook. A reader
    is not enough: an upsert has to know where each key already is, and the
    marks have to be read before they can be retired."""

    def backup(self, path: Path) -> Path | None: ...

    def ensure_sheet(self, path: Path, sheet: str, *, seed: str | None) -> None: ...

    def upsert(
        self,
        path: Path,
        sheet: str,
        *,
        headers: Sequence[str],
        key_header: str,
        rows: Sequence[Mapping[str, str]],
    ) -> UpsertResult: ...

    def fills(self, path: Path, sheet: str, column: str, last_row: int) -> dict[str, str]: ...

    def format(self, path: Path, sheet: str, operations: Sequence[FormatOperation]) -> None: ...

    def cell_text(self, path: Path, sheet: str, cell: str) -> str: ...

    def rich_prepend(
        self,
        path: Path,
        sheet: str,
        cell: str,
        *,
        text: str,
        colour: str,
        tail_colour: str,
        separator: str = "\n",
    ) -> bool: ...

    def set_rich(self, path: Path, sheet: str, cell: str, runs: Sequence[TextRun]) -> None: ...

    def close(self, path: Path, *, save: bool) -> None: ...


def hyperlink_formula(url: str, text: str) -> str:
    """`=HYPERLINK("url","text")`, with Excel's own quote doubling."""
    return (
        f'=HYPERLINK("{url.replace(chr(34), chr(34) * 2)}","{text.replace(chr(34), chr(34) * 2)}")'
    )


def column_letter(index: int) -> str:
    if index < 1:
        raise ValueError("column index is 1-based")
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def header_index(headers: Sequence[str], name: str) -> int:
    """The 1-based column of a header, matched case-insensitively (rule 3).
    Raises `header_missing`, which is a refusal and not a guess."""
    wanted = name.strip().casefold()
    for index, header in enumerate(headers, start=1):
        if str(header).strip().casefold() == wanted:
            return index
    raise WorkbookWriteError("header_missing")


# ---------------------------------------------------------------------------
# Staging
# ---------------------------------------------------------------------------


def owner_file(path: Path) -> Path:
    """Excel's lock file, `~$<name>.xlsx` beside the workbook."""
    return path.with_name("~$" + path.name)


def workbook_is_open(path: Path) -> str | None:
    """Why the workbook looks open to somebody else, or None.

    Deliberately a filesystem check rather than a COM one: it has to be
    answerable *without* opening the file, both before a run and again in the
    seconds before the copy back."""
    if not path.exists():
        return None
    if owner_file(path).exists():
        return "owner_file"
    if not os.access(path, os.W_OK):
        return "read_only_attribute"
    return None


def stage_workbook(real: Path, staging_root: Path) -> Path:
    """Copy the workbook somewhere no sync client is watching, and work
    there. Refuses a workbook somebody has open, before anything is copied."""
    if not real.is_file():
        raise WorkbookWriteError("workbook_missing")
    if workbook_is_open(real) is not None:
        raise WorkbookWriteError("workbook_open")
    staging = staging_root / STAGING_DIR
    try:
        staging.mkdir(parents=True, exist_ok=True)
        staged = staging / real.name
        shutil.copy2(real, staged)
    except OSError:
        raise WorkbookWriteError("workbook_unwritable") from None
    return staged


def unstage_workbook(
    staged: Path, real: Path, *, retry_seconds: float = UNSTAGE_RETRY_SECONDS
) -> None:
    """Put the finished workbook back, or say clearly that it is still
    staged. Called only after a run finished: overwriting the real workbook
    with a half-applied copy would be worse than leaving it alone."""
    if workbook_is_open(real) is not None:
        raise WorkbookWriteError("workbook_open")
    deadline = time.monotonic() + retry_seconds
    while True:
        try:
            shutil.copy2(staged, real)
            return
        except PermissionError:
            if time.monotonic() >= deadline:
                raise WorkbookWriteError("workbook_open") from None
            time.sleep(1.0)
        except OSError:
            raise WorkbookWriteError("workbook_unwritable") from None


# ---------------------------------------------------------------------------
# The one adapter
# ---------------------------------------------------------------------------


def require_com() -> None:
    """Raise where this host cannot drive Excel, so a doctor can ask without
    opening anything.

    Two different absences, kept apart because they are fixed differently.
    `library_missing` is this installation: the bridge is not installed, which
    on a source checkout means the `windows` extra. `excel_missing` is the
    machine: Excel itself is not there. The preview bundle always carries the
    bridge, so an importable `win32com` says nothing at all about Excel, and
    answering "can write it" on the strength of it would promise a write that
    fails at the first `DispatchEx`.

    Resolving the ProgID reads the registry and starts nothing, which is what
    a doctor is allowed to do. Anything other than a clean resolution is read
    as "no Excel here": understating is the safe direction, because the
    preview still runs and only the write is withheld.
    """
    try:
        import pythoncom
        import win32com.client  # noqa: F401 - the adapter's own import
    except ImportError:
        raise WorkbookWriteError("library_missing") from None
    try:
        pythoncom.CLSIDFromProgID("Excel.Application")
    except Exception:
        raise WorkbookWriteError("excel_missing") from None


class ExcelComWriter:
    """The workbook through Excel itself, on the Windows machine that has it.

    Deliberately the only place that knows about COM. It holds the workbook
    open for the whole run, which is what makes a run cheap, and `close`
    releases it: a file the user cannot edit is a worse outcome than the
    failure that caused it.

    **Not exercised by the test suite.** There is no Excel in CI and none on
    a Linux runner, so every test drives a recording writer instead, exactly
    as the source's own tests did. This adapter is written to the documented
    COM object model and is unproven until the owner runs it on a company
    machine; that is recorded in `docs/TASKS.md` beside the model adapters,
    which carry the same caveat.
    """

    def __init__(self, *, visible: bool = False) -> None:
        require_com()
        self._visible = visible
        self._excel: Any = None
        self._books: dict[str, Any] = {}

    # -- Excel's own objects ------------------------------------------

    def _app(self) -> Any:
        if self._excel is None:
            import win32com.client

            self._excel = win32com.client.DispatchEx("Excel.Application")
            self._excel.Visible = self._visible
            self._excel.DisplayAlerts = False
            # A workbook that asks about links or recovery would hang a run
            # nobody is watching.
            self._excel.AskToUpdateLinks = False
            # The team's workbooks may carry macros, and opening one would
            # otherwise run its `Workbook_Open` inside a job the member is
            # not watching. The pinned source Bridge suppresses events for
            # exactly this reason and this is the parity baseline
            # (`host-bridge/app/services/excel_com.py`). Screen updating is
            # off for the same run's sake: it is the slow part of driving
            # Excel cell by cell.
            self._excel.EnableEvents = False
            self._excel.ScreenUpdating = False
        return self._excel

    def _book(self, path: Path) -> Any:
        key = str(path.resolve())
        if key not in self._books:
            if not path.is_file():
                raise WorkbookWriteError("workbook_missing")
            try:
                self._books[key] = self._app().Workbooks.Open(key, UpdateLinks=0)
            except Exception:  # noqa: BLE001 - COM raises its own kinds
                raise WorkbookWriteError("workbook_open") from None
        return self._books[key]

    def _sheet(self, path: Path, sheet: str) -> Any:
        book = self._book(path)
        for index in range(1, int(book.Worksheets.Count) + 1):
            worksheet = book.Worksheets(index)
            if str(worksheet.Name) == sheet:
                return worksheet
        raise WorkbookWriteError("sheet_missing")

    @staticmethod
    def _bgr(colour: str) -> int:
        """Excel takes BGR, not RGB."""
        red, green, blue = (int(colour[i : i + 2], 16) for i in (1, 3, 5))
        return blue * 65536 + green * 256 + red

    @staticmethod
    def _used_last_row(worksheet: Any) -> int:
        """Rule 1: the used range, so hidden rows count."""
        used = worksheet.UsedRange
        return int(used.Row) + int(used.Rows.Count) - 1

    def _headers(self, worksheet: Any) -> list[str]:
        used = worksheet.UsedRange
        width = int(used.Column) + int(used.Columns.Count) - 1
        out: list[str] = []
        for column in range(1, width + 1):
            value = worksheet.Cells(1, column).Value
            out.append("" if value is None else str(value).strip())
        return out

    # -- the protocol -------------------------------------------------

    def backup(self, path: Path) -> Path | None:
        if not path.is_file():
            raise WorkbookWriteError("workbook_missing")
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = path.with_name(f"{path.stem}.backup-{stamp}{path.suffix}")
        try:
            shutil.copy2(path, target)
        except OSError:
            raise WorkbookWriteError("workbook_unwritable") from None
        return target

    def ensure_sheet(self, path: Path, sheet: str, *, seed: str | None) -> None:
        book = self._book(path)
        names = {str(book.Worksheets(i).Name) for i in range(1, int(book.Worksheets.Count) + 1)}
        if sheet in names:
            return
        try:
            if seed and seed in names:
                # A copy, so the member opens the scratch sheet and sees last
                # week's report to edit rather than a blank grid.
                source = self._sheet(path, seed)
                source.Copy(After=book.Worksheets(int(book.Worksheets.Count)))
                book.Worksheets(int(book.Worksheets.Count)).Name = sheet
            else:
                book.Worksheets.Add(After=book.Worksheets(int(book.Worksheets.Count))).Name = sheet
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("write_failed") from None

    def upsert(
        self,
        path: Path,
        sheet: str,
        *,
        headers: Sequence[str],
        key_header: str,
        rows: Sequence[Mapping[str, str]],
    ) -> UpsertResult:
        worksheet = self._sheet(path, sheet)
        existing = self._headers(worksheet)
        if not any(existing):
            for index, header in enumerate(headers, start=1):
                worksheet.Cells(1, index).Value = header
            existing = list(headers)
        # Rule 2: only managed headers, and only those the sheet has.
        managed = {name: header_index(existing, name) for name in headers if _has(existing, name)}
        key_column = header_index(existing, key_header)
        last = self._used_last_row(worksheet)
        placed: dict[str, int] = {}
        for row in range(2, last + 1):
            value = worksheet.Cells(row, key_column).Value
            key = plain_key("" if value is None else str(value))
            if key:
                placed[key] = row  # later duplicates win, as the source did
        inserted = updated = 0
        next_row = max(2, last + 1)
        try:
            for record in rows:
                key = str(record.get(key_header, "")).strip()
                if not key:
                    continue
                if key in placed:
                    target, updated = placed[key], updated + 1
                else:
                    target, placed[key] = next_row, next_row
                    next_row, inserted = next_row + 1, inserted + 1
                for name, column in managed.items():
                    if name == key_header:
                        # The key cell becomes a formula later; writing the
                        # bare key first keeps a failed run readable.
                        worksheet.Cells(target, column).Value = key
                        continue
                    worksheet.Cells(target, column).Value = record.get(name, "")
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("write_failed") from None
        return UpsertResult(
            inserted=inserted,
            updated=updated,
            rows={key: placed[key] for key in (str(r.get(key_header, "")) for r in rows) if key},
            last_row=max(last, next_row - 1),
        )

    def fills(self, path: Path, sheet: str, column: str, last_row: int) -> dict[str, str]:
        worksheet = self._sheet(path, sheet)
        out: dict[str, str] = {}
        for row in range(2, max(2, last_row) + 1):
            cell = worksheet.Range(f"{column}{row}")
            # An unfilled cell reports white, so only ColorIndex says "none".
            if int(cell.Interior.ColorIndex) == -4142:
                continue
            value = int(cell.Interior.Color)
            blue, green, red = value // 65536, (value // 256) % 256, value % 256
            out[f"{column}{row}"] = f"#{red:02X}{green:02X}{blue:02X}"
        return out

    def format(self, path: Path, sheet: str, operations: Sequence[FormatOperation]) -> None:
        worksheet = self._sheet(path, sheet)
        try:
            for operation in operations:
                if isinstance(operation, Fill):
                    target = worksheet.Range(operation.range)
                    if operation.colour is None:
                        target.Interior.ColorIndex = -4142
                    else:
                        target.Interior.Color = self._bgr(operation.colour)
                elif isinstance(operation, FontColour):
                    worksheet.Range(operation.range).Font.Color = self._bgr(operation.colour)
                elif isinstance(operation, Border):
                    target = worksheet.Range(operation.range)
                    # Edge by edge, never the whole collection: setting
                    # `Borders.LineStyle` also draws Excel's two diagonals,
                    # which is not what a table row looks like. xlInside* is
                    # only meaningful for a range spanning more than one cell.
                    edges = [*_EDGE_BORDERS]
                    if ":" in operation.range:
                        edges.append(_INSIDE_VERTICAL)
                    for edge in edges:
                        border = target.Borders(edge)
                        border.LineStyle = -4142 if operation.style == "none" else 1
                        if operation.style != "none":
                            border.Weight = 2 if operation.style == "thin" else -4138
                else:
                    worksheet.Range(operation.cell).Formula = operation.formula
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("write_failed") from None

    def cell_text(self, path: Path, sheet: str, cell: str) -> str:
        value = self._sheet(path, sheet).Range(cell).Value
        return "" if value is None else str(value)

    def rich_prepend(
        self,
        path: Path,
        sheet: str,
        cell: str,
        *,
        text: str,
        colour: str,
        tail_colour: str,
        separator: str = "\n",
    ) -> bool:
        """Put `text` at the top of the cell in `colour`, forcing the older
        text to `tail_colour`, and say whether anything was added.

        Two runs, not N, for the reason the source measured: reading a
        character's colour costs 10-45 ms whatever the cell's length, so a
        2000-character scan took 73 seconds. Reassigning the value destroys
        every run, so the old colour cannot be preserved per run anyway; the
        tail is forced instead, which is also what stops last week's red from
        creeping over the whole history."""
        worksheet = self._sheet(path, sheet)
        target = worksheet.Range(cell)
        current = target.Value
        current = "" if current is None else str(current).replace("\r\n", "\n").replace("\r", "\n")
        head = text if text.endswith("\n") else text + separator
        if current.lstrip().startswith(text.strip()[:24]):
            return False  # already at the top; the caller recolours instead
        try:
            target.Value = head + current
            target.Characters(1, len(head)).Font.Color = self._bgr(colour)
            if current:
                target.Characters(len(head) + 1, len(current)).Font.Color = self._bgr(tail_colour)
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("write_failed") from None
        return True

    def set_rich(self, path: Path, sheet: str, cell: str, runs: Sequence[TextRun]) -> None:
        worksheet = self._sheet(path, sheet)
        target = worksheet.Range(cell)
        try:
            target.Value = "".join(run.text for run in runs)
            start = 1
            for run in runs:
                if run.text:
                    target.Characters(start, len(run.text)).Font.Color = self._bgr(run.colour)
                    start += len(run.text)
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("write_failed") from None

    def close(self, path: Path, *, save: bool) -> None:
        """Save, then release. Saving may fail the run; releasing may not.

        `Close(SaveChanges=True)` would fold the two together, and a failed
        save would then be swallowed with the release it is bundled with: the
        caller would copy an unchanged workbook back and report a report it
        never wrote. Saving explicitly is also what the pinned source Bridge
        does, and it is what keeps a macro workbook's format: `Save` writes
        the file it opened, where `SaveAs` would have to be told which format
        that was.

        A save that cannot be done after retrying loses the run's work: the
        workbook is released regardless, because an invisible Excel holding a
        file the member cannot see is a worse outcome than the failure. The
        staged copy that remains is the one from before the run.
        """
        key = str(path.resolve())
        book = self._books.pop(key, None)
        failure: WorkbookWriteError | None = None
        if book is not None:
            if save:
                failure = self._save(book)
            try:
                book.Close(SaveChanges=False)
            except Exception:  # noqa: BLE001 - releasing is best effort
                pass
        if not self._books and self._excel is not None:
            try:
                self._excel.Quit()
            except Exception:  # noqa: BLE001
                pass
            self._excel = None
        if failure is not None:
            raise failure

    def _save(self, book: Any) -> WorkbookWriteError | None:
        """Save, retrying a lock the way the copy back does.

        Everything after this point discards the run's work: the workbook is
        released either way, because leaving an invisible Excel holding a
        file the member cannot see is worse than the failure. So a lock that
        clears in two seconds must not cost the whole run, exactly as for
        `unstage_workbook`, and for the same reason: something else on the
        machine holds the file for a moment at a time.
        """
        deadline = time.monotonic() + SAVE_RETRY_SECONDS
        while True:
            try:
                book.Save()
            except Exception:  # noqa: BLE001 - COM raises its own kinds
                if time.monotonic() >= deadline:
                    return WorkbookWriteError("save_failed")
                time.sleep(0.5)
            else:
                return None


def _has(headers: Sequence[str], name: str) -> bool:
    try:
        header_index(headers, name)
    except WorkbookWriteError:
        return False
    return True


def plain_key(value: str) -> str:
    """A key cell that already holds our `=HYPERLINK(...)` formula still
    reads back as the bare key."""
    text = value.strip()
    if text.upper().startswith("=HYPERLINK("):
        parts = text.split('"')
        if len(parts) >= 4:
            return parts[3].strip()
    return text
