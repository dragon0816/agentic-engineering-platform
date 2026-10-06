from pathlib import Path
import csv
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment

workspace = Path.cwd()
input_path = workspace / 'input' / 'mixed.csv'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'converted.xlsx'

# Read CSV using utf-8-sig to transparently support a UTF-8 BOM, and newline=''
# so Python's csv module handles quoted commas and embedded newlines correctly.
with input_path.open('r', encoding='utf-8-sig', newline='') as f:
    rows = list(csv.reader(f))

if not rows:
    raise SystemExit('mixed.csv is empty')

headers = rows[0]
try:
    device_id_idx = headers.index('Device ID')
except ValueError:
    device_id_idx = None

def convert_non_device(value):
    """Keep blanks blank; convert plain numbers for Excel, leave text unchanged."""
    if value == '':
        return None
    # Convert simple numeric values only when doing so will not change textual form.
    # This keeps Chinese, quoted commas, and embedded newlines as text.
    s = value.strip()
    if s == value:
        # Integers without leading zeros, and decimal values.
        try:
            if s.isdigit() and (s == '0' or not s.startswith('0')):
                return int(s)
            # cautious float conversion for non-integer numeric strings
            if any(ch in s for ch in '.eE'):
                num = float(s)
                return num
        except ValueError:
            pass
    return value

wb = Workbook()
ws = wb.active
ws.title = 'mixed'

for r_idx, row in enumerate(rows, start=1):
    for c_idx, value in enumerate(row, start=1):
        if device_id_idx is not None and c_idx == device_id_idx + 1 and r_idx > 1:
            cell_value = None if value == '' else str(value)
            cell = ws.cell(row=r_idx, column=c_idx, value=cell_value)
            cell.number_format = '@'
            cell.data_type = 's' if cell_value is not None else 'n'
        else:
            cell_value = None if (r_idx == 1 and value == '') else convert_non_device(value)
            ws.cell(row=r_idx, column=c_idx, value=cell_value)

# Set the whole Device ID column as text format as well, including the header column cells.
if device_id_idx is not None:
    col_letter = ws.cell(row=1, column=device_id_idx + 1).column_letter
    for cell in ws[col_letter]:
        cell.number_format = '@'

# Preserve display of embedded newlines.
for row in ws.iter_rows():
    for cell in row:
        if isinstance(cell.value, str) and '\n' in cell.value:
            cell.alignment = Alignment(wrap_text=True)

wb.save(output_path)
print(f'wrote: {output_path}')
print(f'input rows including header: {len(rows)}')
print(f'headers: {headers}')
print('all source rows:')
for i, row in enumerate(rows, 1):
    print(i, row)

# Verification from the saved output file.
wb2 = load_workbook(output_path, data_only=False)
ws2 = wb2.active
saved_rows = []
for row in ws2.iter_rows(min_row=1, max_row=ws2.max_row, max_col=len(headers), values_only=False):
    saved_rows.append([cell.value if cell.value is not None else '' for cell in row])

# Build expected rows using the same blank policy and numeric conversion for non-Device columns.
expected_rows = []
for r_idx, row in enumerate(rows, start=1):
    expected_row = []
    for c_idx, value in enumerate(row, start=1):
        if device_id_idx is not None and c_idx == device_id_idx + 1 and r_idx > 1:
            expected_row.append(value)
        else:
            expected_row.append('' if value == '' else convert_non_device(value))
    expected_rows.append(expected_row)

checks = []
checks.append(('output file exists', output_path.exists()))
checks.append(('sheet name is mixed', ws2.title == 'mixed'))
checks.append(('row count preserved', ws2.max_row == len(rows)))
checks.append(('column count preserved', ws2.max_column == len(headers)))
checks.append(('headers/order preserved', [ws2.cell(1, c).value for c in range(1, len(headers)+1)] == headers))
checks.append(('all rows/order/duplicates/values preserved', saved_rows == expected_rows))
if device_id_idx is not None:
    device_col = device_id_idx + 1
    device_values = [ws2.cell(r, device_col).value for r in range(2, ws2.max_row + 1)]
    checks.append(('Device ID values are strings where not blank', all(v is None or isinstance(v, str) for v in device_values)))
    checks.append(('Device ID leading zeros preserved', [v if v is not None else '' for v in device_values] == [row[device_id_idx] for row in rows[1:]]))
    checks.append(('Device ID cells use text format', all(ws2.cell(r, device_col).number_format == '@' for r in range(2, ws2.max_row + 1))))
checks.append(('empty CSV fields saved as blank cells', all((cell.value is None) for row in ws2.iter_rows() for cell in row if False)))
# Specific blank check against source empty fields.
blank_ok = True
for r_idx, row in enumerate(rows, start=1):
    for c_idx, value in enumerate(row, start=1):
        if value == '' and ws2.cell(r_idx, c_idx).value is not None:
            blank_ok = False
checks.append(('empty source fields are blank in workbook', blank_ok))

print('verification:')
for name, ok in checks:
    print(f'- {name}: {ok}')
if not all(ok for _, ok in checks):
    raise SystemExit('verification failed')
print('saved rows from workbook:')
for i, row in enumerate(saved_rows, 1):
    print(i, row)
print('Device ID cell types/formats:', [(ws2.cell(r, device_id_idx+1).value, type(ws2.cell(r, device_id_idx+1).value).__name__, ws2.cell(r, device_id_idx+1).number_format) for r in range(2, ws2.max_row+1)] if device_id_idx is not None else 'no Device ID')