"""Workflow 10 sheet replacement against a recording Excel stand-in."""

from pathlib import Path
from typing import Any

import pytest

from capabilities.chipset_report.ruleset import ChipsetRuleset, compile_rules
from integrations import excel_writer
from integrations.chipset_excel import ChipsetExcelWriter
from integrations.excel_writer import WorkbookWriteError


class _RecordingPart:
    events: list[tuple[str, str, Any]]
    address: str
    name: str

    def __init__(self, events: list[tuple[str, str, Any]], address: str, name: str) -> None:
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "address", address)
        object.__setattr__(self, "name", name)

    def __setattr__(self, key: str, value: Any) -> None:
        self.events.append((self.address, f"{self.name}.{key}", value))


class _RecordingRange:
    events: list[tuple[str, str, Any]]
    address: str

    def __init__(self, events: list[tuple[str, str, Any]], address: str) -> None:
        object.__setattr__(self, "events", events)
        object.__setattr__(self, "address", address)
        object.__setattr__(self, "Interior", _RecordingPart(events, address, "Interior"))
        object.__setattr__(self, "Font", _RecordingPart(events, address, "Font"))
        object.__setattr__(self, "Borders", _RecordingPart(events, address, "Borders"))

    def __setattr__(self, key: str, value: Any) -> None:
        self.events.append((self.address, key, value))


class _RecordingUsedRange:
    def __init__(self, events: list[tuple[str, str, Any]]) -> None:
        self.events = events
        self.Value2 = "old data"

    def Clear(self) -> None:  # noqa: N802 - Excel spelling
        self.events.append(("UsedRange", "Clear", None))


class _RecordingColumns:
    def __init__(self, events: list[tuple[str, str, Any]], spec: str) -> None:
        self.events = events
        self.spec = spec

    def AutoFit(self) -> None:  # noqa: N802 - Excel spelling
        self.events.append((self.spec, "AutoFit", None))


class _RecordingSheet:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, Any]] = []
        self.UsedRange = _RecordingUsedRange(self.events)

    def Cells(self, row: int, column: int) -> tuple[int, int]:  # noqa: N802
        return row, column

    def Range(  # noqa: N802
        self, start: str | tuple[int, int], end: tuple[int, int] | None = None
    ) -> _RecordingRange:
        if isinstance(start, tuple):
            assert end is not None
            left = excel_writer.column_letter(start[1])
            right = excel_writer.column_letter(end[1])
            address = f"{left}{start[0]}:{right}{end[0]}"
        else:
            address = start
        return _RecordingRange(self.events, address)

    def Columns(self, spec: str) -> _RecordingColumns:  # noqa: N802
        return _RecordingColumns(self.events, spec)


def _writer(monkeypatch: pytest.MonkeyPatch, worksheet: _RecordingSheet) -> ChipsetExcelWriter:
    monkeypatch.setattr(excel_writer, "require_com", lambda: None)
    writer = ChipsetExcelWriter()
    monkeypatch.setattr(writer, "sheet_names", lambda _path: ("other", "temp"))
    monkeypatch.setattr(writer, "_sheet", lambda _path, _sheet: worksheet)
    return writer


def test_replace_preserves_source_format_order_and_writes_only_the_temp_sheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _RecordingSheet()
    writer = _writer(monkeypatch, sheet)
    path = tmp_path / "copy.xlsm"
    headers = ("Chipset Vendor", "Status", "Purchased Schedule")
    records = ({"Chipset Vendor": "Q", "Status": "new", "Purchased Schedule": "Q4"},)
    metadata = ({"_Match": "tracked", "_Changed": "Purchased Schedule"},)
    rules = compile_rules(ChipsetRuleset())

    count = writer.replace(path, "temp", headers, records, rules, format_records=metadata)

    assert count == 1
    assert sheet.events[0] == ("UsedRange", "Clear", None)
    assert sheet.events[1] == (
        "A1:C2",
        "Value2",
        (headers, ("Q", "new", "Q4")),
    )
    row_fill = ("A2:C2", "Interior.Color", writer._bgr(rules.colours.tracked))
    changed_fill = ("C2:C2", "Interior.Color", writer._bgr(rules.colours.changed))
    assert sheet.events.index(row_fill) < sheet.events.index(changed_fill)
    assert ("A1:C1", "Interior.Color", writer._bgr(rules.colours.header)) in sheet.events
    assert ("A1:C1", "Font.Bold", True) in sheet.events
    assert ("A1:C1", "Borders.LineStyle", 1) in sheet.events
    assert ("A1:C2", "WrapText", True) in sheet.events
    assert ("C2:C2", "Font.Bold", True) in sheet.events
    assert sheet.events[-1] == ("A:C", "AutoFit", None)


def test_protected_sheet_is_refused_before_opening_excel(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _RecordingSheet()
    writer = _writer(monkeypatch, sheet)
    with pytest.raises(ValueError, match="protected_sheet"):
        writer.replace(
            tmp_path / "copy.xlsm",
            "  CHIPSET_REQUIREMENT  ",
            ("Status",),
            (),
            compile_rules(ChipsetRuleset()),
        )
    assert sheet.events == []


def test_replace_refuses_metadata_mismatch_before_clearing_sheet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _RecordingSheet()
    writer = _writer(monkeypatch, sheet)
    with pytest.raises(ValueError, match="format_records_length"):
        writer.replace(
            tmp_path / "copy.xlsm",
            "temp",
            ("Status",),
            ({"Status": "new"},),
            compile_rules(ChipsetRuleset()),
            format_records=(),
        )
    assert sheet.events == []


def test_hidden_trace_requires_format_metadata_before_writing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _RecordingSheet()
    writer = _writer(monkeypatch, sheet)
    with pytest.raises(ValueError, match="format_records_missing_match"):
        writer.replace(
            tmp_path / "copy.xlsm",
            "temp",
            ("Status",),
            ({"Status": "new"},),
            compile_rules(ChipsetRuleset()),
        )
    assert sheet.events == []


def test_com_failure_is_a_stable_write_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sheet = _RecordingSheet()
    writer = _writer(monkeypatch, sheet)

    def broken(*_args: Any) -> _RecordingRange:
        raise OSError("sensitive workbook path")

    monkeypatch.setattr(sheet, "Range", broken)
    with pytest.raises(WorkbookWriteError) as caught:
        writer.replace(
            tmp_path / "copy.xlsm",
            "temp",
            ("Status",),
            ({"Status": "new", "_Match": "new"},),
            compile_rules(ChipsetRuleset()),
        )
    assert caught.value.code == "write_failed"
    assert str(caught.value) == "write_failed"
