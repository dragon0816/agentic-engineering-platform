from pathlib import Path
import csv
from openpyxl import Workbook

workspace = Path.cwd()
input_path = workspace / "input" / "results.csv"
output_dir = workspace / "output"
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / "failed_items.xlsx"

# Read CSV as text values to preserve leading zeros and original field contents.
rows = []
with input_path.open("r", newline="", encoding="utf-8-sig") as f:
    reader = csv.DictReader(f)
    if reader.fieldnames is None:
        fieldnames = []
    else:
        fieldnames = list(reader.fieldnames)
    if "Status" not in fieldnames:
        raise ValueError("CSV does not contain required 'Status' column")
    for row in reader:
        status = row.get("Status", "")
        if status.strip().lower() == "fail":
            rows.append(row)

wb = Workbook()
ws = wb.active
ws.title = "failed_items"

# Write all columns in the original order.
for col_idx, name in enumerate(fieldnames, start=1):
    ws.cell(row=1, column=col_idx, value=name)

for row_idx, row in enumerate(rows, start=2):
    for col_idx, name in enumerate(fieldnames, start=1):
        value = row.get(name, "")
        cell = ws.cell(row=row_idx, column=col_idx, value=value)
        if name == "Device ID":
            cell.number_format = "@"
            cell.value = "" if value is None else str(value)

# Mark entire Device ID column as text too, including header/blank future cells.
if "Device ID" in fieldnames:
    device_col = fieldnames.index("Device ID") + 1
    for r in range(1, ws.max_row + 1):
        ws.cell(row=r, column=device_col).number_format = "@"

wb.save(output_path)
print(f"Read: {input_path}")
print(f"Filtered failed rows: {len(rows)}")
print(f"Wrote: {output_path}")
print(f"Columns: {fieldnames}")