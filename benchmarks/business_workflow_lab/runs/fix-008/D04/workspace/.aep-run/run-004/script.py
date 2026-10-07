from pathlib import Path
import csv, shutil
from decimal import Decimal, ROUND_HALF_UP
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

ws = Path.cwd()
input_dir = ws / 'input'
output_dir = ws / 'output'
output_dir.mkdir(exist_ok=True)

employee = 'E006'
start_date = '2026-01-01'
end_date = '2026-01-31'
source_name = 'Expense Viewer (synthetic lab)'
generated_at = '2026-10-06T00:00:00+08:00'

export_csv = output_dir / f'expense_{employee}_{start_date}_{end_date}.csv'
if not export_csv.exists():
    raise FileNotFoundError(f'Expected successful export file is missing: {export_csv}')
if export_csv.stat().st_size <= 0:
    raise ValueError(f'Export file exists but is empty: {export_csv}')

print('Inputs really present:')
print(' - template:', (input_dir/'expense_template.xlsx').exists(), input_dir/'expense_template.xlsx')
print(' - fx rates:', (input_dir/'fx_rates.csv').exists(), input_dir/'fx_rates.csv')
print(' - exported csv:', export_csv.exists(), export_csv, 'bytes', export_csv.stat().st_size)

# Read export
with export_csv.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    source_headers = reader.fieldnames or []
    rows = list(reader)
print('Export headers:', source_headers)
print('Export row count:', len(rows))
print('Export sample rows:', rows[:3])

required_export_headers = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','Status','ReceiptID','Description','MissingReceipt']
if source_headers != required_export_headers:
    raise ValueError(f'Unexpected export headers: {source_headers}')

# Read FX rates robustly because Note contains comma in the test file
rates = {}
with (input_dir/'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row or not row[0]:
            continue
        rates[row[0]] = Decimal(row[1])
print('FX rates:', rates)

# Validate/filter rows from successful export. Query already filtered in the app; this verifies delivered criteria.
filtered = []
exceptions = []
for r in rows:
    if r.get('EmployeeID') != employee or not (start_date <= r.get('ExpenseDate','') <= end_date):
        raise ValueError(f'Export contains row outside requested filter: {r}')
    filtered.append(r)

# Fill a copy of the actual template, preserving workbook structure/styles.
template = input_dir / 'expense_template.xlsx'
out_xlsx = output_dir / f'expense_report_{employee}_{start_date}_to_{end_date}.xlsx'
shutil.copyfile(template, out_xlsx)
wb = load_workbook(out_xlsx)

# Keep expected sheet names and headers
expected_sheets = ['Report', 'Details', 'Summary', 'Exceptions', 'Instructions']
if wb.sheetnames != expected_sheets:
    raise ValueError(f'Unexpected template sheets: {wb.sheetnames}')

report = wb['Report']
details = wb['Details']
summary = wb['Summary']
exceptions_ws = wb['Exceptions']

# Report sheet
report['B3'] = start_date
report['D3'] = end_date
report['B4'] = f'EmployeeID={employee}; ExpenseDate {start_date} to {end_date}; Status=ALL; Project=ALL'
report['B5'] = generated_at
report['B7'] = source_name
report['D7'] = generated_at
if filtered:
    report['B9'] = f'成功匯出並處理 {len(filtered)} 筆資料。'
else:
    report['B9'] = '查無符合條件的資料（0 筆）；已產出保留表頭、無明細列的正常空報表。'

# Helpers
ROUND = Decimal('0.01')
def money(v):
    return Decimal(str(v)).quantize(ROUND, rounding=ROUND_HALF_UP)

def amount_twd(amount, currency):
    if currency not in rates:
        raise ValueError(f'Missing FX rate for currency {currency}')
    return (Decimal(str(amount)) * rates[currency]).quantize(ROUND, rounding=ROUND_HALF_UP)

def truthy(v):
    return str(v).strip().lower() in {'true','1','yes','y'}

# Clear any old data rows from copied template, preserving row 4 headers.
def clear_from_row(wsht, start=5):
    if wsht.max_row >= start:
        wsht.delete_rows(start, wsht.max_row - start + 1)

clear_from_row(details, 5)
clear_from_row(summary, 5)
clear_from_row(exceptions_ws, 5)

# Details rows
for idx, r in enumerate(filtered, start=5):
    amt = money(r['Amount'])
    twd = amount_twd(amt, r['Currency'])
    missing = 'true' if truthy(r.get('MissingReceipt','')) else 'false'
    needs_review = 'true' if missing == 'true' or r.get('Status') in {'Rejected', 'Draft'} else 'false'
    vals = [
        r.get('ExpenseID') or None,
        r.get('EmployeeID') or None,
        r.get('EmployeeName') or None,
        r.get('ProjectID') or None,
        r.get('ExpenseDate') or None,
        r.get('Category') or None,
        r.get('Currency') or None,
        float(amt),
        float(twd),
        r.get('Status') or None,
        r.get('ReceiptID') or None,
        r.get('Description') or None,
        missing,
        needs_review,
    ]
    for col, val in enumerate(vals, start=1):
        c = details.cell(row=idx, column=col, value=val)
        if col in {1,2,4,11}:  # IDs as text
            c.number_format = '@'
        elif col == 5:
            c.number_format = 'yyyy-mm-dd'
        elif col in {8,9}:
            c.number_format = '0.00'
    if needs_review == 'true':
        exceptions.append((r.get('ExpenseID') or None, r.get('EmployeeID') or None, r.get('ExpenseDate') or None, 'Missing receipt' if missing == 'true' else f"Status {r.get('Status')} needs review"))

# Summary: group by Status, Currency if there are rows; no data rows for zero records.
if filtered:
    groups = {}
    for r in filtered:
        key = (r.get('Status') or '', r.get('Category') or '', r.get('Currency') or '')
        amt = money(r['Amount'])
        twd = amount_twd(amt, r['Currency'])
        cur_amt, cur_twd, count = groups.get(key, (Decimal('0'), Decimal('0'), 0))
        groups[key] = (cur_amt + amt, cur_twd + twd, count + 1)
    for idx, (key, vals) in enumerate(sorted(groups.items()), start=5):
        status, category, currency = key
        amt_sum, twd_sum, count = vals
        data = [status, category, currency, float(amt_sum.quantize(ROUND)), float(twd_sum.quantize(ROUND)), count]
        for col, val in enumerate(data, start=1):
            c = summary.cell(row=idx, column=col, value=val)
            if col in {4,5}:
                c.number_format = '0.00'
    last_detail_row = 4 + len(filtered)
    summary['B2'] = f'=SUM(Details!I5:I{last_detail_row})'
else:
    summary['B2'] = '=SUM(Details!I5:I5)'

# Exceptions, no rows if empty/no exceptions
for idx, ex in enumerate(exceptions, start=5):
    for col, val in enumerate(ex, start=1):
        c = exceptions_ws.cell(row=idx, column=col, value=val)
        if col in {1,2}:
            c.number_format = '@'
        elif col == 3:
            c.number_format = 'yyyy-mm-dd'

# Preserve headers; ensure text-like ID columns are text in first potential row formatting too.
for wsht in (details, exceptions_ws):
    for col in range(1, wsht.max_column + 1):
        wsht.cell(row=4, column=col).font = Font(bold=True)

wb.save(out_xlsx)
print('Saved report:', out_xlsx)

# Reopen and verify all stated requirements from saved outputs.
wb2 = load_workbook(out_xlsx, data_only=False)
assert wb2.sheetnames == expected_sheets
rpt = wb2['Report']; det = wb2['Details']; summ = wb2['Summary']; exc = wb2['Exceptions']
assert rpt['B3'].value == start_date
assert rpt['D3'].value == end_date
assert employee in str(rpt['B4'].value)
assert rpt['B5'].value == generated_at
assert rpt['B7'].value == source_name
assert rpt['D7'].value == generated_at
assert '0 筆' in str(rpt['B9'].value)
assert det.max_row == 4, f'Details should have only header rows for empty report, max_row={det.max_row}'
assert summ.max_row == 4, f'Summary should have only header rows for empty report, max_row={summ.max_row}'
assert exc.max_row == 4, f'Exceptions should have only header rows for empty report, max_row={exc.max_row}'
assert summ['B2'].value == '=SUM(Details!I5:I5)'
assert [det.cell(4,c).value for c in range(1,15)] == ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
assert [summ.cell(4,c).value for c in range(1,7)] == ['Group','SubGroup','Currency','Amount','AmountTWD','Count']
assert [exc.cell(4,c).value for c in range(1,5)] == ['ExpenseID','EmployeeID','ExpenseDate','Reason']
assert export_csv.exists() and export_csv.stat().st_size > 0
with export_csv.open(newline='', encoding='utf-8-sig') as f:
    vr = csv.DictReader(f)
    vrows = list(vr)
assert vr.fieldnames == required_export_headers
assert len(vrows) == 0
print('Verification passed:')
print(' - successful exported CSV exists and has expected headers with 0 data rows')
print(' - workbook copied from template, sheet names preserved')
print(' - Report period/condition/source/generated fields populated')
print(' - Details/Summary/Exceptions retain headers and have no data rows')
print(' - Summary B2 formula kept for empty report: =SUM(Details!I5:I5)')
print('Output files:', [(p.name, p.stat().st_size) for p in sorted(output_dir.iterdir())])