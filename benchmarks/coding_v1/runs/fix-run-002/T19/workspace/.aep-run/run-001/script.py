from pathlib import Path
import csv
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

workspace = Path.cwd()
input_path = workspace / "input" / "mixed.csv"
output_dir = workspace / "output"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "converted.xlsx"

if not input_path.exists():
    raise FileNotFoundError(f"Input file not found: {input_path}")

wb = Workbook()
ws = wb.active
ws.title = "mixed"

row_count = 0
col_count = 0
headers = []
device_id_col = None

# utf-8-sig handles UTF-8 BOM. newline='' lets csv correctly parse quoted commas/newlines.
with input_path.open("r", encoding="utf-8-sig", newline="") as f:
    reader = csv.reader(f)
    for r_idx, row in enumerate(reader, start=1):
        row_count += 1
        col_count = max(col_count, len(row))
        if r_idx == 1:
            headers = row[:]
            for i, h in enumerate(headers, start=1):
                if h == "Device ID":
                    device_id_col = i
                    break
        for c_idx, value in enumerate(row, start=1):
            # Preserve textual CSV values exactly, including leading zeroes.
            # Empty CSV fields are written as blank cells.
            cell = ws.cell(row=r_idx, column=c_idx)
            if value == "":
                cell.value = None
            else:
                # Excel XML cannot contain illegal control chars; strip only those if present.
                cell.value = ILLEGAL_CHARACTERS_RE.sub("", value)
            if c_idx == device_id_col:
                cell.number_format = "@"
                if value != "":
                    cell.data_type = "s"

# Ensure the Device ID column is formatted as text for all cells, including future/blanks.
if device_id_col is not None:
    col_letter = ws.cell(row=1, column=device_id_col).column_letter
    for cell in ws[col_letter]:
        cell.number_format = "@"
        if cell.value is not None:
            cell.data_type = "s"

wb.save(output_path)
print(f"Created: {output_path}")
print(f"Rows written: {row_count}")
print(f"Max columns written: {col_count}")
print(f"Device ID column: {device_id_col if device_id_col is not None else 'not found'}")