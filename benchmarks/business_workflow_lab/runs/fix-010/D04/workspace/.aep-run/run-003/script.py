from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font
from copy import copy
import csv
from decimal import Decimal, ROUND_HALF_UP

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)

# Known query result from Expense Viewer operation in this run:
employee_id = 'E006'
from_date = '2026-01-01'
to_date = '2026-01-31'
status_filter = ''  # no filter
project_filter = '' # no filter
query_result_count = 0
query_dialog_text = '查無符合條件的資料（0 筆）。'
source_name = 'Expense Viewer (synthetic lab)'
# Operator supplied today date in prompt; no exact clock time was supplied/needed for an empty export-less report.
generated_at = '2026-10-06T00:00:00+08:00'
fetched_at = generated_at

# Read fx_rates just to validate the provided supporting input is usable.
fx_path = input_dir / 'fx_rates.csv'
fx_rates = {}
with fx_path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cur = (row.get('Currency') or '').strip()
        rate = (row.get('RateToTWD') or '').strip()
        if cur:
            fx_rates[cur] = Decimal(rate)
print('fx_rates currencies:', sorted(fx_rates))

# Fill a copy of the supplied template; do not rebuild it.
template_path = input_dir / 'expense_template.xlsx'
out_path = output_dir / 'expense_report_E006_2026-01-01_to_2026-01-31.xlsx'
wb = load_workbook(template_path)

report = wb['Report']
report['B3'] = from_date
report['D3'] = to_date
report['B4'] = 'EmployeeID=E006; ExpenseDate 2026-01-01 to 2026-01-31 inclusive; Status=all; Project=all'
report['B5'] = generated_at
report['B7'] = source_name
report['D7'] = fetched_at
report['B9'] = 'Expense Viewer returned no matching records (0 rows). Export was unavailable/disabled for the empty result, so no export file was used.'

# Keep headers and leave no data rows for zero-row report.
details = wb['Details']
summary = wb['Summary']
exceptions = wb['Exceptions']

# Ensure there are no accidental rows beyond headers in detail sheets.
for ws_name in ['Details', 'Summary', 'Exceptions']:
    ws = wb[ws_name]
    if ws.max_row > 4:
        ws.delete_rows(5, ws.max_row - 4)

# Summary total formula must remain valid for zero rows per instructions.
summary['B2'] = '=SUM(Details!I5:I5)'

# Apply expected text/number/date formats to data ranges if later opened/extended; no data rows here.
# Keep workbook sheets, merges, footer, and instructions untouched.
wb.save(out_path)
print('wrote', out_path)

# Reopen and verify requirements from saved output.
check = load_workbook(out_path, data_only=False)
assert check.sheetnames == ['Report', 'Details', 'Summary', 'Exceptions', 'Instructions'], check.sheetnames
r = check['Report']
assert r['B3'].value == from_date
assert r['D3'].value == to_date
assert 'EmployeeID=E006' in r['B4'].value
assert r['B5'].value == generated_at
assert r['B7'].value == source_name
assert r['D7'].value == fetched_at
assert '0 rows' in r['B9'].value
assert r['A20'].value == '合成測試資料 Synthetic lab data · template v1 · 請勿修改本行'

d = check['Details']
expected_details_headers = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
actual_details_headers = [d.cell(4, c).value for c in range(1, 15)]
assert actual_details_headers == expected_details_headers, actual_details_headers
# no records: no non-empty row from row 5 onward
nonempty_detail_rows = []
for row in d.iter_rows(min_row=5, values_only=True):
    if any(v is not None for v in row):
        nonempty_detail_rows.append(row)
assert len(nonempty_detail_rows) == 0, nonempty_detail_rows

s = check['Summary']
assert s['B2'].value == '=SUM(Details!I5:I5)'
expected_summary_headers = ['Group','SubGroup','Currency','Amount','AmountTWD','Count']
assert [s.cell(4, c).value for c in range(1,7)] == expected_summary_headers
nonempty_summary_rows = []
for row in s.iter_rows(min_row=5, values_only=True):
    if any(v is not None for v in row):
        nonempty_summary_rows.append(row)
assert len(nonempty_summary_rows) == 0, nonempty_summary_rows

e = check['Exceptions']
assert [e.cell(4, c).value for c in range(1,5)] == ['ExpenseID','EmployeeID','ExpenseDate','Reason']
nonempty_exception_rows = []
for row in e.iter_rows(min_row=5, values_only=True):
    if any(v is not None for v in row):
        nonempty_exception_rows.append(row)
assert len(nonempty_exception_rows) == 0, nonempty_exception_rows

# Confirm output exists and is non-empty.
assert out_path.exists() and out_path.stat().st_size > 0
print('checks passed: output exists; template sheets preserved; Report fields filled; Details/Summary/Exceptions headers preserved; zero data rows; Summary B2 zero-row formula retained; footer preserved.')
print('output_file', out_path.name)
