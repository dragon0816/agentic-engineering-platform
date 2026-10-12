from pathlib import Path
from copy import copy
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.worksheet.dimensions import RowDimension

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

template_path = input_dir / 'expense_template.xlsx'
output_path = output_dir / 'expense_report_E006_2026-01-01_2026-01-31.xlsx'

# Parameters from the request and the Expense Viewer query result observed via desktop operation.
employee_id = 'E006'
from_date = '2026-01-01'
to_date = '2026-01-31'
condition = f'EmployeeID={employee_id}; ExpenseDate {from_date} to {to_date}; Status=All; Project=All'
generated_at = '2026-10-06T00:00:00+08:00'
fetched_at = '2026-10-06T00:00:00+08:00'
source = 'Expense Viewer (synthetic lab)'
notes = 'Expense Viewer query returned 0 rows. Export was unavailable/disabled for the empty result, so no export file was produced or used.'

wb = load_workbook(template_path)

# Fill Report sheet while preserving the template.
report = wb['Report']
report['B3'] = from_date
report['D3'] = to_date
report['B4'] = condition
report['B5'] = generated_at
report['B7'] = source
report['D7'] = fetched_at
report['B9'] = notes

# Clear any data rows in detail-like sheets, preserving row 4 headers and template formatting.
def clear_data_rows(ws, start_row=5):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)
    # Keep a single hidden/height-normal row? No: instructions say data begins at row 5 and no blank rows.

for sheet_name in ['Details', 'Exceptions']:
    clear_data_rows(wb[sheet_name], 5)

# Summary: no source rows, so keep the header and a numeric zero total.
summary = wb['Summary']
clear_data_rows(summary, 5)
summary['B2'] = 0
summary['B2'].number_format = '0.00'

# Ensure important ID/date/money formats on data-entry areas even when empty, without creating data rows.
for cell in wb['Details'][4]:
    cell.font = copy(cell.font)
for cell in wb['Exceptions'][4]:
    cell.font = copy(cell.font)

wb.save(output_path)

# Verification: reopen the saved workbook and confirm requirements.
check = load_workbook(output_path, data_only=False)
errors = []
for required in ['Report', 'Details', 'Summary', 'Exceptions', 'Instructions']:
    if required not in check.sheetnames:
        errors.append(f'missing sheet {required}')

r = check['Report']
expected_cells = {
    'B3': from_date,
    'D3': to_date,
    'B4': condition,
    'B5': generated_at,
    'B7': source,
    'D7': fetched_at,
    'B9': notes,
}
for addr, expected in expected_cells.items():
    if r[addr].value != expected:
        errors.append(f'Report!{addr} expected {expected!r}, got {r[addr].value!r}')

details = check['Details']
expected_detail_headers = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
actual_detail_headers = [details.cell(4, c).value for c in range(1, 15)]
if actual_detail_headers != expected_detail_headers:
    errors.append(f'Details headers mismatch: {actual_detail_headers!r}')
if details.max_row != 4:
    errors.append(f'Details should contain headers only for empty result; max_row={details.max_row}')

exceptions = check['Exceptions']
expected_exception_headers = ['ExpenseID','EmployeeID','ExpenseDate','Reason']
actual_exception_headers = [exceptions.cell(4, c).value for c in range(1, 5)]
if actual_exception_headers != expected_exception_headers:
    errors.append(f'Exceptions headers mismatch: {actual_exception_headers!r}')
if exceptions.max_row != 4:
    errors.append(f'Exceptions should contain headers only for empty result; max_row={exceptions.max_row}')

s = check['Summary']
if s['B2'].value != 0:
    errors.append(f'Summary!B2 expected numeric 0, got {s["B2"].value!r}')
if not isinstance(s['B2'].value, (int, float)):
    errors.append('Summary!B2 is not numeric')
if s.max_row != 4:
    errors.append(f'Summary should contain headers only plus total; max_row={s.max_row}')

if not output_path.exists() or output_path.stat().st_size <= 0:
    errors.append('output file missing or empty')

print('output', output_path)
print('output_exists', output_path.exists())
print('output_size', output_path.stat().st_size if output_path.exists() else 0)
print('details_rows_after_header', max(0, details.max_row - 4))
print('exceptions_rows_after_header', max(0, exceptions.max_row - 4))
print('summary_total_B2', s['B2'].value, type(s['B2'].value).__name__)
print('report_condition', r['B4'].value)
print('report_notes', r['B9'].value)
if errors:
    print('VERIFY_FAILED')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print('VERIFY_OK')