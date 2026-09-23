"""The one adapter that drives Excel, against a stand-in for Excel.

The suite has no Excel and CI has none either, so what can be checked here is
what the adapter *asks Excel to do*: the application settings it insists on
before a workbook is opened, and that saving and releasing are separate
questions with separate answers. The rest of the adapter remains unproven
until it runs on a company workstation, which `docs/TASKS.md` records.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest

from integrations.excel_writer import ExcelComWriter, WorkbookWriteError


class FakeBook:
    def __init__(self, *, save_raises: bool = False) -> None:
        self.save_raises = save_raises
        self.saved = 0
        self.closed_with: list[bool] = []

    def Save(self) -> None:  # noqa: N802 - Excel's own spelling
        if self.save_raises:
            raise OSError("the network share went away")
        self.saved += 1

    def Close(self, SaveChanges: bool) -> None:  # noqa: N802, N803 - Excel's own spelling
        self.closed_with.append(SaveChanges)


class FakeWorkbooks:
    def __init__(self, book: FakeBook) -> None:
        self._book = book
        self.opened: list[str] = []

    def Open(self, path: str, UpdateLinks: int = 0) -> FakeBook:  # noqa: N802, N803
        self.opened.append(path)
        return self._book


class FakeExcel:
    def __init__(self, book: FakeBook) -> None:
        self.Workbooks = FakeWorkbooks(book)
        self.settings: dict[str, Any] = {}
        self.quit_calls = 0

    def __setattr__(self, name: str, value: Any) -> None:
        if name in {"Workbooks", "settings", "quit_calls"}:
            super().__setattr__(name, value)
            return
        self.settings[name] = value

    def Quit(self) -> None:  # noqa: N802 - Excel's own spelling
        super().__setattr__("quit_calls", self.quit_calls + 1)


def install(monkeypatch: pytest.MonkeyPatch, book: FakeBook) -> FakeExcel:
    """Stand in for the whole of `pywin32`, which this machine does not have
    and a Linux runner cannot have."""
    excel = FakeExcel(book)
    pythoncom = types.ModuleType("pythoncom")
    pythoncom.CLSIDFromProgID = lambda prog_id: "{00024500-0000-0000-C000-000000000046}"  # type: ignore[attr-defined]
    client = types.ModuleType("win32com.client")
    client.DispatchEx = lambda prog_id: excel  # type: ignore[attr-defined]
    win32com = types.ModuleType("win32com")
    win32com.client = client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "pythoncom", pythoncom)
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    return excel


def opened_writer(tmp_path: Path, excel_book: FakeBook) -> tuple[ExcelComWriter, Path]:
    workbook = tmp_path / "book.xlsm"
    workbook.write_bytes(b"not really a workbook")
    writer = ExcelComWriter()
    writer._book(workbook)  # the adapter's own way in; nothing else opens a file
    return writer, workbook


def test_a_workbooks_macros_do_not_run_because_this_opened_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A team workbook may carry macros, and `Workbook_Open` would otherwise
    run inside a job nobody is watching. The pinned source Bridge suppresses
    events for the same reason, and it is the parity baseline."""
    excel = install(monkeypatch, FakeBook())
    opened_writer(tmp_path, FakeBook())
    assert excel.settings["EnableEvents"] is False
    assert excel.settings["ScreenUpdating"] is False
    assert excel.settings["DisplayAlerts"] is False
    assert excel.settings["AskToUpdateLinks"] is False


def test_saving_and_releasing_are_asked_separately(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`Close(SaveChanges=True)` would fold them together, and the release is
    best effort. Saving is not."""
    book = FakeBook()
    install(monkeypatch, book)
    writer, workbook = opened_writer(tmp_path, book)
    writer.close(workbook, save=True)
    assert book.saved == 1
    assert book.closed_with == [False], "the save already happened; the close must not redo it"


def test_a_workbook_that_was_not_saved_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect this exists for: a failed save used to be swallowed with
    the release it was bundled with, and the caller then copied an unchanged
    workbook back and reported a report it had never written."""
    book = FakeBook(save_raises=True)
    excel = install(monkeypatch, book)
    writer, workbook = opened_writer(tmp_path, book)
    with pytest.raises(WorkbookWriteError) as refused:
        writer.close(workbook, save=True)
    assert refused.value.code == "save_failed"
    assert book.closed_with == [False], "the workbook is still released"
    assert excel.quit_calls == 1, "and Excel still quits, or EXCEL.EXE outlives the run"


def test_a_release_without_a_save_asks_for_neither(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A run that failed part way releases the workbook and keeps its
    changes out of the file."""
    book = FakeBook(save_raises=True)
    install(monkeypatch, book)
    writer, workbook = opened_writer(tmp_path, book)
    writer.close(workbook, save=False)
    assert book.saved == 0
    assert book.closed_with == [False]
