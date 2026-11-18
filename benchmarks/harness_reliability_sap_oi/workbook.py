"""Fallback author after reproducible native Artifact XLSX export unavailability.

Formula caches are explicit snapshots, not evidence of desktop Excel recalculation.
"""

import json
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from html import escape
from pathlib import Path
from typing import Any, cast
from xml.etree import ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo
from openpyxl.worksheet.worksheet import Worksheet

from .pivot_package import HEADERS, S, add_pivot


def build_workbook(path: Path, records: list[dict[str, Any]], source: str) -> None:
    book = Workbook()
    pivot = cast(Worksheet, book.active)
    pivot.title = "OI Pivot"
    data = book.create_sheet("OI Data")
    data.append(HEADERS)
    totals: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for i, row in enumerate(records, 2):
        amount = Decimal(str(row["amount"])) * Decimal(str(row["fx"]))
        totals[row["sales"], row["month"]] += amount
        data.append(
            [
                row["document"],
                row["line"],
                datetime.strptime(row["created_at"], "%Y-%m-%d %H:%M:%S"),
                row["sales"],
                row["customer"],
                row["status"],
                row["currency"],
                row["amount"],
                row["fx"],
                row["month"],
                f"=H{i}*I{i}",
            ]
        )
        data.cell(i, 3).number_format = "yyyy-mm-dd hh:mm:ss"
        for column_index in (8, 9, 11):
            data.cell(i, column_index).number_format = "#,##0.00"
    table = Table(displayName="OIData", ref=f"A1:K{len(records) + 1}")
    table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
    data.add_table(table)
    data.cell(16, 1, f"Source: {source} — fictional data. CreatedAt uses Asia/Taipei local time.")
    data.cell(17, 1, "Test FX: USD to TWD 32, TWD to TWD 1. No live exchange rates.")
    data.cell(
        18, 1, "Formula caches are calculated snapshots. Confirm Excel refresh on a company PC."
    )
    data.freeze_panes = "A2"
    sales = sorted({r["sales"] for r in records})
    months = sorted({r["month"] for r in records})
    pivot["B2"] = "OI by Sales and Month (TWD)"
    pivot["B3"] = "2026-09-01 to 2026-10-31 inclusive, Asia/Taipei"
    pivot["B4"] = "Booked OI lines, including signed adjustments and zero amounts"
    matrix: list[list[Any]] = [["Sales", *months, "Grand Total"]]
    for person in sales:
        amounts = [float(totals[person, month]) for month in months]
        matrix.append([person, *amounts, sum(amounts)])
    column_totals = [sum(float(totals[person, month]) for person in sales) for month in months]
    matrix.append(["Grand Total", *column_totals, sum(column_totals)])
    for r, summary_row in enumerate(matrix, 6):
        for c, value in enumerate(summary_row, 2):
            cell = pivot.cell(r, c, value)
            if c > 2 and r > 6:
                cell.number_format = "#,##0.00"
    for sheet in (pivot, data):
        sheet.sheet_view.showGridLines = False
        for styled_row in sheet:
            for cell in styled_row:
                cell.font = Font(name="Arial", size=11)
                cell.alignment = Alignment(vertical="center")
            sheet.row_dimensions[cast(int, styled_row[0].row)].height = 23
    pivot["B2"].font = Font(name="Arial", size=16, bold=True)
    for cell in pivot[6][1:5]:
        cell.fill = PatternFill("solid", fgColor="224B77")
        cell.font = Font(name="Arial", size=11, color="FFFFFF", bold=True)
        cell.alignment = Alignment(horizontal="center", vertical="center")
    for cell in pivot[10][1:5]:
        cell.font = Font(name="Arial", size=11, bold=True)
    for column in ("B", "C", "D", "E"):
        pivot.column_dimensions[column].width = 24 if column == "B" else 20
    for column in "ABCDEFGHIJK":
        data.column_dimensions[column].width = 21
    data.column_dimensions["C"].width = 25
    data.column_dimensions["E"].width = 25
    for cell in data[1]:
        cell.fill = PatternFill("solid", fgColor="224B77")
        cell.font = Font(name="Arial", size=11, color="FFFFFF", bold=True)
    book.save(path)
    book.close()
    # Supply transparent, deterministic cached values for readers without Excel.
    with ZipFile(path) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    xml_sheet = ET.fromstring(parts["xl/worksheets/sheet2.xml"])
    for i, row in enumerate(records, 2):
        xml_cell = xml_sheet.find(f"{{{S}}}sheetData/{{{S}}}row/{{{S}}}c[@r='K{i}']")
        if xml_cell is None:
            raise ValueError("conversion_formula_missing")
        xml_value = xml_cell.find(f"{{{S}}}v")
        if xml_value is None:
            xml_value = ET.SubElement(xml_cell, f"{{{S}}}v")
        xml_value.text = str(Decimal(str(row["amount"])) * Decimal(str(row["fx"])))
    parts["xl/worksheets/sheet2.xml"] = ET.tostring(xml_sheet, encoding="utf-8")
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, payload in parts.items():
            archive.writestr(name, payload)
    add_pivot(path, records)


def saved_cell_snapshot(path: Path) -> Path:
    values = load_workbook(path, data_only=True)
    formulas = load_workbook(path, data_only=False)
    snapshots = []
    try:
        for sheet in values:
            matrix = []
            for row in sheet:
                cells = []
                for cell in row:
                    value = cell.value
                    if isinstance(value, datetime):
                        value = (value - datetime(1899, 12, 30)).total_seconds() / 86400
                    cells.append(value)
                matrix.append(cells)
            expressions = [
                (cell.coordinate, cell.value)
                for row in formulas[sheet.title]
                for cell in row
                if cell.data_type == "f"
            ]
            snapshots.append({"name": sheet.title, "values": matrix, "formulas": expressions})
    finally:
        values.close()
        formulas.close()
    output = path.parent / "saved-cell-snapshot.json"
    output.write_text(json.dumps(snapshots), encoding="utf-8")
    return output


def review_html(path: Path) -> Path:
    book = load_workbook(path, data_only=True)
    parts = [
        '<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><style>',
        "body{font:14px Arial;color:var(--foreground,#17263b);background:transparent}",
        "table{border-collapse:collapse;margin-bottom:24px;white-space:nowrap}",
        "td,th{padding:8px 12px;border-bottom:1px solid var(--border,#ddd);text-align:left}",
        "th{background:var(--secondary,#e9eff6)}.scroll{overflow:auto}h2{font-size:18px}",
        "</style><p>實際儲存格預覽（非 Microsoft Excel 畫面）。"
        "原生樞紐定義與快取另由驗收器檢查。</p>",
    ]
    try:
        for sheet in book:
            parts.extend([f'<h2>{escape(sheet.title)}</h2><div class="scroll"><table>'])
            region = (
                sheet.iter_rows(min_row=6, max_row=10, min_col=2, max_col=5)
                if sheet.title == "OI Pivot"
                else sheet.iter_rows(min_row=1, max_row=13, max_col=11)
            )
            for i, row in enumerate(region):
                parts.append("<tr>")
                for cell in row:
                    value = cell.value
                    if isinstance(value, datetime):
                        display = value.strftime("%Y-%m-%d %H:%M:%S")
                    elif isinstance(value, (int, float)):
                        display = f"{value:,.2f}"
                    else:
                        display = str(value or "")
                    tag = "th" if i == 0 else "td"
                    parts.append(f"<{tag}>{escape(display)}</{tag}>")
                parts.append("</tr>")
            parts.append("</table></div>")
    finally:
        book.close()
    parts.append("</html>")
    output = path.parent / "workbook-review.html"
    output.write_text("".join(parts), encoding="utf-8")
    return output
