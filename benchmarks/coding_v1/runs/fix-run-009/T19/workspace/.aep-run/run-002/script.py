from pathlib import Path
import csv
from openpyxl import Workbook, load_workbook
from openpyxl.styles import numbers

workspace = Path.cwd()
input_path = workspace / 'input' / 'mixed.csv'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'converted.xlsx'

# Read CSV with utf-8-sig so an optional UTF-8 BOM is handled, and newline='' so
# quoted commas/newlines are interpreted by csv.reader correctly.
with input_path.open('r', encoding='utf-8-sig', newline='') as f:
    rows = list(csv.reader(f))

if not rows:
    raise ValueError('mixed.csv is empty; cannot create workbook with headers')

headers = rows[0]
try:
    device_col_idx_0 = headers.index('Device ID')
except ValueError as exc:
    raise ValueError('Required column "Device ID" was not found') from exc

wb = Workbook()
ws = wb.active
ws.title = 'converted'

for r_idx, row in enumerate(rows, start=1):
    # csv.reader preserves duplicate rows and order. Pad short rows only if malformed;
    # fail on unexpected column counts to avoid silently changing the structure.
    if len(row) != len(headers):
        raise ValueError(f'Row {r_idx} has {len(row)} columns; expected {len(headers)}')
    for c_idx, value in enumerate(row, start=1):
        cell = ws.cell(row=r_idx, column=c_idx)
        if value == '':
            # Keep CSV empty fields as truly blank Excel cells.
            cell.value = None
        else:
            # Preserve CSV text exactly. In particular, Device ID remains text with leading zeros.
            cell.value = str(value)
        if c_idx == device_col_idx_0 + 1:
            cell.number_format = '@'

# Save the workbook.
wb.save(output_path)
print('created:', output_path)
print('source rows including header:', len(rows))
print('source columns:', len(headers), headers)

# Verification: reopen output file and confirm every stated requirement.
wb2 = load_workbook(output_path, data_only=False)
ws2 = wb2.active

# Read exactly the same rectangle as the CSV, normalizing blank Excel cells back to ''.
out_rows = []
for row in ws2.iter_rows(min_row=1, max_row=len(rows), min_col=1, max_col=len(headers)):
    out_rows.append(['' if cell.value is None else cell.value for cell in row])

errors = []
if output_path.name != 'converted.xlsx':
    errors.append('Output filename is not converted.xlsx')
if ws2.max_column != len(headers):
    errors.append(f'Column count changed: {ws2.max_column} != {len(headers)}')
if ws2.max_row != len(rows):
    errors.append(f'Row count changed: {ws2.max_row} != {len(rows)}')
if out_rows != rows:
    errors.append('Workbook cell values do not exactly match CSV values/order/duplicates after blank normalization')
if out_rows[0] != headers:
    errors.append('Headers changed')
if len(out_rows) != len(rows):
    errors.append('Row count including duplicate rows changed')
# Confirm the explicit duplicate data row is retained when present.
if len(rows) > 4 and rows[1] == rows[4] and out_rows[1] != out_rows[4]:
    errors.append('Duplicate row was not preserved')
# Confirm Device ID cells are text and leading zeros remain.
for excel_row_num in range(2, len(rows) + 1):
    src_value = rows[excel_row_num - 1][device_col_idx_0]
    cell = ws2.cell(row=excel_row_num, column=device_col_idx_0 + 1)
    out_value = '' if cell.value is None else cell.value
    if src_value != out_value:
        errors.append(f'Device ID mismatch at row {excel_row_num}: {out_value!r} != {src_value!r}')
    if src_value != '' and not isinstance(cell.value, str):
        errors.append(f'Device ID is not text at row {excel_row_num}: {type(cell.value).__name__}')
    if src_value.startswith('0') and out_value != src_value:
        errors.append(f'Device ID leading zero not preserved at row {excel_row_num}: {out_value!r}')
    if cell.number_format != '@':
        errors.append(f'Device ID cell number format is not text at row {excel_row_num}')
# Confirm no added index column by exact header count/name sequence.
if headers != [ws2.cell(row=1, column=i).value for i in range(1, len(headers) + 1)]:
    errors.append('Header order/names changed, possibly index column added')
# Confirm quoted comma and newline examples survived, if present in source.
flat_values = [v for row in out_rows for v in row]
if '含, 逗號' not in flat_values:
    errors.append('Quoted comma field was not preserved')
if '第一行\n第二行' not in flat_values:
    errors.append('Quoted newline field was not preserved')
# Confirm blank fields stayed blank.
for r_i, row in enumerate(rows, start=1):
    for c_i, src_value in enumerate(row, start=1):
        if src_value == '' and ws2.cell(row=r_i, column=c_i).value is not None:
            errors.append(f'Blank value is not blank at row {r_i}, col {c_i}')

if errors:
    print('verification FAILED:')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)

print('verification OK')
print('checked: output filename, headers, column order/count, row count, duplicate rows, exact cell values, quoted comma/newline fields, blank cells, Device ID text format and leading zeros, no index column')
print('output rows including header:', ws2.max_row)
print('output columns:', ws2.max_column)
print('sample output rows:')
for row in out_rows[:6]:
    print(row)