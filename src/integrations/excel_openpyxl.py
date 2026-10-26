"""A `WorkbookWriter` over openpyxl, for writing a *copy* of a workbook.

The weekly report's real writer is `ExcelComWriter`: Excel itself, because
openpyxl rewrites the whole file and drops what it does not model (charts,
pivot caches, some conditional formats). That loss is acceptable for a
preview copy a person opens to check a week before the real run, and for
nothing else, so this adapter is only ever handed a copy
(`capabilities.weekly_report.preview`). It speaks the same protocol, so the
executor in `capabilities.weekly_report.apply` runs unchanged: the preview
workbook is written by the same plan, in the same order, as the real one.

Two differences from the COM adapter, both in what openpyxl can express:

* A key cell is a real cell hyperlink (`cell.hyperlink`), which is what the
  workbook's own weekly sheets hold, rather than a `=HYPERLINK()` formula.
  The COM adapter avoids hyperlink objects only because they leak COM
  references; openpyxl has none. The cell keeps its fill, border and
  alignment; its font gains the underline and blue of a link.
* Rich text is written as openpyxl `CellRichText` runs.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from integrations.excel_writer import (
    Alignment,
    Border,
    Fill,
    FontColour,
    FormatOperation,
    Hyperlink,
    TextRun,
    UpsertResult,
    WorkbookWriteError,
    header_index,
    plain_key,
)

#: Excel's own Hyperlink style colour.
LINK_COLOUR = "FF0563C1"


def _library() -> Any:
    try:
        import openpyxl
    except ImportError:
        raise WorkbookWriteError("library_missing") from None
    return openpyxl


def _argb(colour: str) -> str:
    return "FF" + colour.lstrip("#").upper()


class OpenpyxlWorkbookWriter:
    """One workbook file at a time, loaded once and saved on `close`."""

    def __init__(self) -> None:
        self._books: dict[str, Any] = {}

    # -- the file --------------------------------------------------------

    def _book(self, path: Path) -> Any:
        key = str(path.resolve())
        book = self._books.get(key)
        if book is None:
            if not path.is_file():
                raise WorkbookWriteError("workbook_missing")
            try:
                book = _library().load_workbook(path, rich_text=True)
            except WorkbookWriteError:
                raise
            except Exception:  # noqa: BLE001 - whatever openpyxl raises for a bad file
                raise WorkbookWriteError("write_failed") from None
            self._books[key] = book
        return book

    def _sheet(self, path: Path, sheet: str) -> Any:
        book = self._book(path)
        if sheet not in book.sheetnames:
            raise WorkbookWriteError("sheet_missing")
        return book[sheet]

    def sheet_names(self, path: Path) -> tuple[str, ...]:
        return tuple(str(name) for name in self._book(path).sheetnames)

    def backup(self, path: Path) -> Path | None:
        # Only ever handed a copy: the copy is the backup.
        if not path.is_file():
            raise WorkbookWriteError("workbook_missing")
        return None

    def ensure_sheet(self, path: Path, sheet: str, *, seed: str | None) -> None:
        book = self._book(path)
        if sheet in book.sheetnames:
            return
        try:
            if seed and seed in book.sheetnames:
                made = book.copy_worksheet(book[seed])
                made.title = sheet
            else:
                book.create_sheet(sheet)
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("write_failed") from None

    # -- rows ------------------------------------------------------------

    @staticmethod
    def _headers(worksheet: Any) -> list[str]:
        if worksheet.max_row < 1:
            return []
        return [
            "" if cell.value is None else str(cell.value).strip()
            for cell in next(worksheet.iter_rows(min_row=1, max_row=1))
        ]

    @staticmethod
    def _last_row(worksheet: Any) -> int:
        """The last row holding anything, hidden rows included (rule 1)."""
        for row in range(worksheet.max_row, 0, -1):
            if any(
                worksheet.cell(row, column).value not in (None, "")
                for column in range(1, worksheet.max_column + 1)
            ):
                return row
        return 0

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
                worksheet.cell(1, index).value = header
            existing = list(headers)
        managed: dict[str, int] = {}
        for name in headers:
            try:
                managed[name] = header_index(existing, name)
            except WorkbookWriteError:
                continue
        key_column = header_index(existing, key_header)
        last = self._last_row(worksheet)
        placed: dict[str, int] = {}
        for row in range(2, last + 1):
            value = worksheet.cell(row, key_column).value
            key = plain_key("" if value is None else str(value))
            if key:
                placed[key] = row
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
                    worksheet.cell(target, column).value = (
                        key if name == key_header else record.get(name, "")
                    )
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
            cell = worksheet[f"{column}{row}"]
            fill = cell.fill
            if fill is None or fill.fill_type != "solid":
                continue
            rgb = getattr(fill.fgColor, "rgb", None)
            if isinstance(rgb, str) and len(rgb) == 8:
                out[f"{column}{row}"] = f"#{rgb[2:].upper()}"
        return out

    # -- formats ---------------------------------------------------------

    @staticmethod
    def _cells(worksheet: Any, reference: str) -> list[Any]:
        found = worksheet[reference]
        if not isinstance(found, tuple):
            return [found]
        cells: list[Any] = []
        for row in found:
            if isinstance(row, tuple):
                cells.extend(row)
            else:
                cells.append(row)
        return cells

    def format(self, path: Path, sheet: str, operations: Sequence[FormatOperation]) -> None:
        _library()
        from openpyxl import styles

        worksheet = self._sheet(path, sheet)
        try:
            for operation in operations:
                if isinstance(operation, Fill):
                    for cell in self._cells(worksheet, operation.range):
                        cell.fill = (
                            styles.PatternFill(fill_type=None)
                            if operation.colour is None
                            else styles.PatternFill(
                                fill_type="solid",
                                fgColor=_argb(operation.colour),
                                bgColor=_argb(operation.colour),
                            )
                        )
                elif isinstance(operation, FontColour):
                    for cell in self._cells(worksheet, operation.range):
                        font = copy.copy(cell.font)
                        font.color = _argb(operation.colour)
                        cell.font = font
                        value = cell.value
                        if _is_rich(value):
                            # A colour on the cell does not reach runs that
                            # carry their own, which is every run we wrote.
                            cell.value = _rich(
                                cell, [TextRun(text=str(value), colour=operation.colour)]
                            )
                elif isinstance(operation, Alignment):
                    for cell in self._cells(worksheet, operation.range):
                        cell.alignment = styles.Alignment(
                            horizontal=operation.horizontal,
                            vertical=operation.vertical,
                            wrap_text=operation.wrap_text,
                        )
                elif isinstance(operation, Border):
                    side = (
                        styles.Side(style=None)
                        if operation.style == "none"
                        else styles.Side(style=operation.style)
                    )
                    for cell in self._cells(worksheet, operation.range):
                        cell.border = styles.Border(left=side, right=side, top=side, bottom=side)
                elif isinstance(operation, Hyperlink):
                    cell = worksheet[operation.cell]
                    cell.value = operation.text
                    cell.hyperlink = operation.url
                    font = copy.copy(cell.font)
                    font.underline = "single"
                    font.color = LINK_COLOUR
                    cell.font = font
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("write_failed") from None

    def sort_highlighted_rows(
        self,
        path: Path,
        sheet: str,
        *,
        key_column: str,
        last_column: str,
        last_row: int,
        colour: str,
    ) -> None:
        """Highlighted rows first, every row moving whole (values, styles,
        links, height and hidden state), in their order otherwise: what
        Excel's stable colour sort does."""
        if last_row < 3:
            return
        _library()
        from openpyxl.utils import column_index_from_string

        worksheet = self._sheet(path, sheet)
        width = max(column_index_from_string(last_column), worksheet.max_column)
        wanted = _argb(colour)
        try:
            snapshots = []
            for row in range(2, last_row + 1):
                cells = []
                for column in range(1, width + 1):
                    cell = worksheet.cell(row, column)
                    link = cell.hyperlink.target if cell.hyperlink is not None else None
                    cells.append((cell.value, copy.copy(cell._style), link))
                dimension = worksheet.row_dimensions[row]
                fill = worksheet[f"{key_column}{row}"].fill
                tinted = (
                    fill is not None
                    and fill.fill_type == "solid"
                    and getattr(fill.fgColor, "rgb", None) == wanted
                )
                snapshots.append((not tinted, cells, dimension.height, dimension.hidden))
            ordered = sorted(snapshots, key=lambda entry: entry[0])
            for offset, (_, cells, height, hidden) in enumerate(ordered):
                row = 2 + offset
                for column, (value, style, link) in enumerate(cells, start=1):
                    cell = worksheet.cell(row, column)
                    cell.value = value
                    cell._style = copy.copy(style)
                    cell.hyperlink = link
                worksheet.row_dimensions[row].height = height
                worksheet.row_dimensions[row].hidden = hidden
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("write_failed") from None

    # -- text ------------------------------------------------------------

    def cell_text(self, path: Path, sheet: str, cell: str) -> str:
        value = self._sheet(path, sheet)[cell].value
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
        target = self._sheet(path, sheet)[cell]
        current = "" if target.value is None else str(target.value)
        current = current.replace("\r\n", "\n").replace("\r", "\n")
        head = text if text.endswith("\n") else text + separator
        if current.lstrip().startswith(text.strip()[:24]):
            return False
        runs = [TextRun(text=head, colour=colour)]
        if current:
            runs.append(TextRun(text=current, colour=tail_colour))
        try:
            target.value = _rich(target, runs)
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("write_failed") from None
        return True

    def set_rich(self, path: Path, sheet: str, cell: str, runs: Sequence[TextRun]) -> None:
        target = self._sheet(path, sheet)[cell]
        try:
            target.value = _rich(target, runs)
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("write_failed") from None

    def close(self, path: Path, *, save: bool) -> None:
        book = self._books.pop(str(path.resolve()), None)
        if book is None:
            return
        try:
            if save:
                book.save(path)
        except Exception:  # noqa: BLE001
            raise WorkbookWriteError("save_failed") from None
        finally:
            book.close()


def _is_rich(value: object) -> bool:
    return type(value).__name__ == "CellRichText"


def _rich(cell: Any, runs: Sequence[TextRun]) -> Any:
    """Runs in the cell's own font, each in its colour."""
    _library()
    from openpyxl.cell.rich_text import CellRichText, TextBlock
    from openpyxl.cell.text import InlineFont
    from openpyxl.styles.colors import Color

    base = cell.font
    blocks = [
        TextBlock(InlineFont(rFont=base.name, sz=base.sz, color=Color(_argb(run.colour))), run.text)
        for run in runs
        if run.text
    ]
    return CellRichText(blocks)
