"""Reading a workbook without Excel.

`openpyxl` reads the file's bytes: it never starts Excel and, used as it is
here, never writes. The import is lazy so a host without the `office` extra
still loads this module and reports the capability unavailable rather than
raising at import time. Nothing here writes a workbook; how the platform
writes one is a decision recorded in the Phase 7 documents, not made here.
"""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Literal

WorkbookErrorCode = Literal[
    "library_missing",
    "workbook_missing",
    "workbook_unreadable",
    "sheet_missing",
]


class WorkbookError(Exception):
    """The code is the whole message; no path, sheet or cell is echoed."""

    def __init__(self, code: WorkbookErrorCode) -> None:
        self.code: WorkbookErrorCode = code
        super().__init__(code)


def _openpyxl() -> Any:
    try:
        import openpyxl
    except ImportError:
        raise WorkbookError("library_missing") from None
    return openpyxl


def require_library() -> None:
    """Raise `library_missing` when openpyxl is not installed; a doctor asks
    this without opening any file."""
    _openpyxl()


def _open(path: Path) -> Any:
    library = _openpyxl()
    if not path.is_file():
        raise WorkbookError("workbook_missing")
    try:
        return library.load_workbook(path, read_only=True, data_only=True)
    except Exception:  # noqa: BLE001 - whatever openpyxl raises for a bad file
        raise WorkbookError("workbook_unreadable") from None


def sheet_names(path: Path) -> tuple[str, ...]:
    workbook = _open(path)
    try:
        return tuple(str(name) for name in workbook.sheetnames)
    finally:
        workbook.close()


def read_rows(path: Path, sheet: str) -> tuple[tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """`(headers, rows)` of one sheet, every value as the text a cell shows
    and an empty cell as `""`. Row 1 is the header row."""
    workbook = _open(path)
    try:
        if sheet not in workbook.sheetnames:
            raise WorkbookError("sheet_missing")
        worksheet = workbook[sheet]
        iterator = worksheet.iter_rows(values_only=True)
        headers = _texts(next(iterator, ()))
        rows = tuple(_texts(row) for row in iterator)
    finally:
        workbook.close()
    return headers, rows


def read_chosen_sheet(
    path: Path, choose: Callable[[tuple[str, ...]], str | None]
) -> tuple[tuple[str, ...], str | None, tuple[str, ...], tuple[tuple[str, ...], ...]]:
    """The sheet names, the sheet `choose` picks from them, and that
    sheet's headers and rows, from one open of the file: a 75-sheet workbook
    is parsed once, not once per question."""
    workbook = _open(path)
    try:
        names = tuple(str(name) for name in workbook.sheetnames)
        source = choose(names)
        if source is None:
            return names, None, (), ()
        if source not in names:
            raise WorkbookError("sheet_missing")
        iterator = workbook[source].iter_rows(values_only=True)
        headers = _texts(next(iterator, ()))
        rows = tuple(_texts(row) for row in iterator)
    finally:
        workbook.close()
    return names, source, headers, rows


def _texts(row: Sequence[Any]) -> tuple[str, ...]:
    return tuple("" if value is None else str(value) for value in row)
