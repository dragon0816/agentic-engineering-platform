"""Workflow 10's one-sheet Excel replacement, adapted from the source Bridge.

The source job calls ``excel_write(mode='replace')`` on its temporary sheet,
then ``excel_format`` with a load-bearing operation order.  This adapter
uses the platform's existing Excel COM lifecycle, including macro/event
suppression and explicit save/close, while keeping that sheet operation intact.
The caller owns staging, backup and the final save decision.
"""

from collections.abc import Mapping, Sequence
from pathlib import Path

from capabilities.chipset_report.rules import UNRESOLVED_TECHNOLOGY, header_key
from capabilities.chipset_report.ruleset import Rules
from integrations.excel_writer import ExcelComWriter, WorkbookWriteError, column_letter

_MAX_CELL_CHARS = 32_767
_MAX_COLUMNS = 16_384
_MAX_ROWS = 1_048_576
_PROTECTED_SHEET = "chipset_requirement"


def _cell_value(value: str | int | float | None) -> str | int | float | None:
    """Match the source Bridge's string marshalling into Excel ``Value2``."""
    if isinstance(value, str):
        return value.replace("\r\n", "\n").replace("\r", "\n")[:_MAX_CELL_CHARS]
    return value


def _row_colour(record: Mapping[str, object], rules: Rules) -> str:
    colours = rules.colours
    if UNRESOLVED_TECHNOLOGY in str(record.get("_Warnings") or ""):
        return colours.unresolved
    match = record.get("_Match", "new")
    if match == "tracked":
        return colours.tracked
    if match in ("partial", "tracked-other-tech"):
        return colours.partial
    return colours.new


class ChipsetExcelWriter(ExcelComWriter):
    """Replace only Workflow 10's temp sheet; never touch its managed sheet.

    ``format_records`` carries source match/change metadata when the user has
    disabled trace columns in the visible output.  It is parallel to
    ``records`` and is never written into the workbook.
    """

    def replace(
        self,
        path: Path,
        sheet: str,
        headers: Sequence[str],
        records: Sequence[Mapping[str, str | int | float]],
        rules: Rules,
        *,
        format_records: Sequence[Mapping[str, object]] | None = None,
    ) -> int:
        if sheet.strip().casefold() == _PROTECTED_SHEET:
            raise ValueError("protected_sheet")
        if not headers:
            raise ValueError("headers_empty")
        if len(headers) > _MAX_COLUMNS or len(records) + 1 > _MAX_ROWS:
            raise ValueError("excel_grid_exceeded")
        source_metadata: Sequence[Mapping[str, object]] = (
            format_records if format_records is not None else records
        )
        if len(source_metadata) != len(records):
            raise ValueError("format_records_length")
        if any("_Match" not in record for record in source_metadata):
            raise ValueError("format_records_missing_match")

        # Resolve by Excel's case-insensitive sheet identity before changing
        # anything.  The source Bridge also matches names this way.
        try:
            names = self.sheet_names(path)
            actual = next(
                (name for name in names if name.strip().casefold() == sheet.strip().casefold()),
                None,
            )
            if actual is None:
                self.ensure_sheet(path, sheet, seed=None)
                actual = sheet
            worksheet = self._sheet(path, actual)
            used = worksheet.UsedRange
            used.Clear()  # source mode=replace; other sheets are not addressed

            rows: tuple[tuple[str | int | float | None, ...], ...] = (
                tuple(_cell_value(header) for header in headers),
                *(
                    tuple(_cell_value(record.get(header)) for header in headers)
                    for record in records
                ),
            )
            last_column = column_letter(len(headers))
            last_row = len(records) + 1
            worksheet.Range(
                worksheet.Cells(1, 1), worksheet.Cells(last_row, len(headers))
            ).Value2 = rows

            # Preserve the source's exact format order.  Row colour must be
            # assigned before a changed-field cell's more specific colour.
            header_range = worksheet.Range(f"A1:{last_column}1")
            header_range.Interior.Pattern = 1  # xlSolid
            header_range.Interior.Color = self._bgr(rules.colours.header)
            header_range.Font.Bold = True
            header_range.Borders.LineStyle = 1  # xlContinuous
            header_range.Borders.Weight = 2  # xlThin
            worksheet.Range(f"A1:{last_column}{last_row}").WrapText = True
            columns = {header_key(header): index for index, header in enumerate(headers, start=1)}
            for offset, metadata in enumerate(source_metadata, start=2):
                row_range = worksheet.Range(f"A{offset}:{last_column}{offset}")
                row_range.Interior.Pattern = 1
                row_range.Interior.Color = self._bgr(_row_colour(metadata, rules))
                for field in str(metadata.get("_Changed") or "").split(","):
                    column = columns.get(header_key(field.strip()))
                    if column is None:
                        continue
                    letter = column_letter(column)
                    cell = worksheet.Range(f"{letter}{offset}:{letter}{offset}")
                    cell.Interior.Pattern = 1
                    cell.Interior.Color = self._bgr(rules.colours.changed)
                    cell.Font.Bold = True
            worksheet.Columns(f"A:{last_column}").AutoFit()
        except WorkbookWriteError:
            raise
        except Exception:  # noqa: BLE001 - pywin32 raises many COM exception kinds
            raise WorkbookWriteError("write_failed") from None
        return len(records)
