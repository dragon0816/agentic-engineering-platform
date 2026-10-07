from pathlib import Path
import csv
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font

workspace = Path.cwd()
input_path = workspace / 'input' / 'mixed.csv'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'converted.xlsx'

# Read the CSV using utf-8-sig to support UTF-8 BOM and newline='' so quoted newlines parse correctly.
with input_path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    rows = list(reader)

if not rows:
    raise ValueError('mixed.csv is empty; cannot create workbook with headers')

headers = rows[0]
try:
    device_id_col = headers.index('Device ID') + 1  # 1-based for openpyxl
except ValueError:
    device_id_col = None

wb = Workbook()
ws = wb.active
ws.title = 'Sheet1'

for r_idx, row in enumerate(rows, start=1):
    # Preserve exact column count from the header; csv rows are written as-is.
    for c_idx, value in enumerate(row, start=1):
        cell = ws.cell(row=r_idx, column=c_idx)
        if value == '':
            cell.value = None  # blank cell for empty values
        else:
            cell.value = value
        if c_idx == device_id_col:
            cell.number_format = '@'  # Excel text format; keeps leading zero display

# Make headers plain text as provided; no index column added.
wb.save(output_path)
print('wrote:', output_path)
print('source rows including header:', len(rows))
print('source columns:', len(headers), headers)

# Verification: reopen source and output; check all stated requirements.
wb2 = load_workbook(output_path, data_only=False)
ws2 = wb2.active

# Build values from output. Convert blank cells back to '' for comparison to CSV empties.
out_rows = []
for r in range(1, ws2.max_row + 1):
    out_row = []
    for c in range(1, ws2.max_column + 1):
        v = ws2.cell(r, c).value
        out_row.append('' if v is None else v)
    out_rows.append(out_row)

errors = []
if output_path.name != 'converted.xlsx':
    errors.append('output file name is not converted.xlsx')
if out_rows != rows:
    errors.append('output cell values do not exactly match CSV rows after blank-cell normalization')
if ws2.max_column != len(headers):
    errors.append(f'column count mismatch: {ws2.max_column} != {len(headers)}')
if out_rows[0] != headers:
    errors.append('headers changed')
if len(out_rows) != len(rows):
    errors.append(f'row count mismatch: {len(out_rows)} != {len(rows)}')
if len(rows) >= 5 and out_rows[1] != out_rows[4]:
    errors.append('duplicate rows were not preserved at rows 2 and 5')
if device_id_col is not None:
    for r in range(2, ws2.max_row + 1):
        src_value = rows[r-1][device_id_col-1] if device_id_col-1 < len(rows[r-1]) else ''
        cell = ws2.cell(r, device_id_col)
        out_value = '' if cell.value is None else cell.value
        if src_value != out_value:
            errors.append(f'Device ID value mismatch at row {r}: {out_value!r} != {src_value!r}')
        if src_value != '' and not isinstance(cell.value, str):
            errors.append(f'Device ID not stored as text at row {r}: {type(cell.value).__name__}')
        if src_value != '' and cell.number_format != '@':
            errors.append(f'Device ID cell not formatted as text at row {r}: {cell.number_format!r}')

# Specific feature checks from the sample/file content.
if len(out_rows) >= 4:
    if out_rows[2][2] != '含, 逗號':
        errors.append('quoted comma field was not preserved')
    if out_rows[3][2] != '第一行\n第二行':
        errors.append('quoted newline field was not preserved')
    if out_rows[3][3] != '':
        errors.append('empty Value cell in row 4 was not blank')
if len(out_rows) >= 6:
    if out_rows[5][1] != '' or out_rows[5][2] != '':
        errors.append('empty Chinese/name or notes cells in row 6 were not blank')

print('\nVerification summary:')
print('output exists:', output_path.exists())
print('worksheet:', ws2.title)
print('rows including header:', ws2.max_row)
print('columns:', ws2.max_column)
print('headers:', out_rows[0])
print('Device ID column:', device_id_col)
print('Device ID values/types/formats:')
if device_id_col is not None:
    for r in range(2, ws2.max_row + 1):
        cell = ws2.cell(r, device_id_col)
        print(f' row {r}: value={cell.value!r}, type={type(cell.value).__name__}, number_format={cell.number_format!r}')
print('duplicate row 2 equals row 5:', len(out_rows) >= 5 and out_rows[1] == out_rows[4])
print('quoted comma preserved:', len(out_rows) >= 3 and out_rows[2][2] == '含, 逗號')
print('quoted newline preserved:', len(out_rows) >= 4 and out_rows[3][2] == '第一行\n第二行')
print('blank cells preserved as blank after normalization:', all((rows[r][c] != '' or out_rows[r][c] == '') for r in range(len(rows)) for c in range(len(rows[r]))))

if errors:
    print('\nERRORS:')
    for e in errors:
        print('-', e)
    raise SystemExit(1)
print('\nAll checks passed.')
