"""The one adapter that drives Excel, against a stand-in for Excel.

The suite has no Excel and CI has none either, so what can be checked here is
what the adapter *asks Excel to do*: the application settings it insists on
before a workbook is opened, and that saving and releasing are separate
questions with separate answers. The rest of the adapter remains unproven
until it runs on a company workstation, which `docs/TASKS.md` records.
"""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path
from typing import Any

import pytest

from integrations import excel_writer
from integrations.excel_writer import ExcelComWriter, WorkbookWriteError


class FakeBook:
    def __init__(self, *, save_raises: bool = False, failures: int = 0) -> None:
        self.save_raises = save_raises
        self.failures = failures
        self.attempts = 0
        self.saved = 0
        self.closed_with: list[bool] = []

    def Save(self) -> None:  # noqa: N802 - Excel's own spelling
        self.attempts += 1
        if self.save_raises or self.attempts <= self.failures:
            raise OSError("the file is locked")
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
    """Stand in for the bridge, which this machine does not have and a Linux
    runner cannot have.

    Only the bridge is faked. Whether Excel is *there* is asked of the real
    registry, and a test that faked that question is what let a made-up API
    through on 2026-09-24.
    """
    excel = FakeExcel(book)
    client = types.ModuleType("win32com.client")
    client.DispatchEx = lambda prog_id: excel  # type: ignore[attr-defined]
    win32com = types.ModuleType("win32com")
    win32com.client = client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    monkeypatch.setattr(excel_writer, "progid_is_registered", lambda _prog_id: True)
    return excel


def opened_writer(tmp_path: Path) -> tuple[ExcelComWriter, Path]:
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
    opened_writer(tmp_path)
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
    writer, workbook = opened_writer(tmp_path)
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
    monkeypatch.setattr(excel_writer, "SAVE_RETRY_SECONDS", 0.0)
    writer, workbook = opened_writer(tmp_path)
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
    writer, workbook = opened_writer(tmp_path)
    writer.close(workbook, save=False)
    assert book.saved == 0
    assert book.closed_with == [False]


def test_a_lock_that_clears_does_not_cost_the_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Everything past a failed save discards the run's work, so a lock that
    clears in a moment must not decide the run. The copy back retries for the
    same reason and for the same length of time."""
    book = FakeBook(failures=2)
    install(monkeypatch, book)
    monkeypatch.setattr(excel_writer, "SAVE_RETRY_SECONDS", 5.0)
    monkeypatch.setattr(time, "sleep", lambda _seconds: None)
    writer, workbook = opened_writer(tmp_path)
    writer.close(workbook, save=True)
    assert book.attempts == 3 and book.saved == 1


def test_whether_a_program_is_registered_is_asked_of_this_machine() -> None:
    """The real registry, on the machine the test runs on.

    This is the test that was missing. The check used to go through the COM
    bridge's own module and call a function that does not exist there, and a
    fake with that function on it passed happily while every real host
    reported that Excel was not installed.
    """
    assert excel_writer.progid_is_registered("Shell.Application") is True, (
        "every Windows machine registers this one"
    )
    assert excel_writer.progid_is_registered("No.Such.Program.Ever") is False
    assert excel_writer.EXCEL_PROGID == "Excel.Application"


def test_a_machine_with_the_bridge_and_no_excel_says_which(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The two absences stay apart: this one is the machine, not the
    installation."""
    client = types.ModuleType("win32com.client")
    win32com = types.ModuleType("win32com")
    win32com.client = client  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "win32com", win32com)
    monkeypatch.setitem(sys.modules, "win32com.client", client)
    with pytest.raises(WorkbookWriteError) as refused:
        excel_writer.require_com()
    assert refused.value.code == "excel_missing", "this machine has no Excel"
