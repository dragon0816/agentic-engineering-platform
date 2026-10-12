from pathlib import Path
import csv, shutil
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from collections import defaultdict
from openpyxl import load_workbook
from openpyxl.styles import Font

WORK = Path('.')
INPUT = WORK/'input'
OUTPUT = WORK/'output'
OUTPUT.mkdir(exist_ok=True)

src_template = INPUT/'expense_template.xlsx'
expense_csv = OUTPUT/'expenses_2026-09_approved.csv'
fx_csv = INPUT/'fx_rates.csv'
out_xlsx = OUTPUT/'expense_report_2026-09_approved.xlsx'

# Read rates
rates = {}
with fx_csv.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        cur = (row.get('Currency') or '').strip()
        rate = (row.get('RateToTWD') or '').strip()
        if cur:
            rates[cur] = Decimal(rate)
print('FX rates:', rates)

# Read exported expenses
rows = []
with expense_csv.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    print('Expense headers:', reader.fieldnames)
    for row in reader:
        rows.append(row)
print('Exported rows:', len(rows))

# Validate filter criteria from exported data
bad = [r for r in rows if not ('2026-09-01' <= r['ExpenseDate'] <= '2026-09-30' and r['Status'] == 'Approved')]
if bad:
    raise SystemExit(f'Found rows outside requested filter: {bad[:3]}')

# Sort stable by date then ExpenseID for report readability
rows.sort(key=lambda r: (r['ExpenseDate'], r['ExpenseID']))

# Prepare workbook copy from template
shutil.copy2(src_template, out_xlsx)
wb = load_workbook(out_xlsx)
ws_report = wb['Report']
ws_details = wb['Details']
ws_summary = wb['Summary']
ws_ex = wb['Exceptions']

# Helper clear rows from row 5 down while preserving sheet objects
def clear_from(ws, start_row=5):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

for ws in [ws_details, ws_summary, ws_ex]:
    clear_from(ws, 5)

# Report metadata
now = datetime.now().astimezone().replace(microsecond=0).isoformat()
ws_report['B3'] = '2026-09-01'
ws_report['D3'] = '2026-09-30'
ws_report['B4'] = 'Expense Viewer: Status=Approved; Date=2026-09-01..2026-09-30'
ws_report['B5'] = now
ws_report['B7'] = 'Expense Viewer desktop export; fx_rates.csv'
ws_report['D7'] = now
ws_report['B9'] = 'AmountTWD = Amount × fixed RateToTWD, ROUND_HALF_UP to 2 decimals. NeedsReview=true when AmountTWD > 5000.'

# Details
headers = [ws_details.cell(4, c).value for c in range(1, ws_details.max_column+1)]
expected = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
if headers != expected:
    raise SystemExit(f'Details headers unexpected: {headers}')

summary = defaultdict(lambda: {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0})
exceptions = []

for i, r in enumerate(rows, start=5):
    cur = r['Currency']
    if cur not in rates:
        raise SystemExit(f'Missing FX rate for {cur}')
    amount = Decimal(r['Amount'])
    amount_twd = (amount * rates[cur]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    needs = amount_twd > Decimal('5000.00')
    vals = [
        r['ExpenseID'], r['EmployeeID'], r['EmployeeName'], r['ProjectID'], r['ExpenseDate'],
        r['Category'], cur, float(amount), float(amount_twd), r['Status'], r.get('ReceiptID') or '',
        r.get('Description') or '', str(r.get('MissingReceipt','')).lower(), 'true' if needs else 'false'
    ]
    for c, v in enumerate(vals, start=1):
        cell = ws_details.cell(i, c, v)
        if c in [1,2,3,4,5,6,7,10,11,12,13,14]:
            cell.number_format = '@'
        elif c in [8,9]:
            cell.number_format = '0.00'
    # Preserve formula-friendly numeric types for amounts; text IDs are strings.
    employee_group = f"{r['EmployeeID']} {r['EmployeeName']}"
    key = (employee_group, r['Category'], cur)
    summary[key]['amount'] += amount
    summary[key]['twd'] += amount_twd
    summary[key]['count'] += 1
    if needs:
        exceptions.append((r['ExpenseID'], r['EmployeeID'], r['ExpenseDate'], f'AmountTWD {amount_twd} > 5000'))

last_detail_row = 4 + len(rows) if rows else 5
ws_summary['B2'] = f'=SUM(Details!I5:I{last_detail_row if rows else 5})'

# Summary rows sorted by employee, category, currency
for out_r, ((employee, category, cur), data) in enumerate(sorted(summary.items()), start=5):
    vals = [employee, category, cur, float(data['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), float(data['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), data['count']]
    for c, v in enumerate(vals, start=1):
        cell = ws_summary.cell(out_r, c, v)
        if c in [1,2,3]:
            cell.number_format = '@'
        elif c in [4,5]:
            cell.number_format = '0.00'
        elif c == 6:
            cell.number_format = '0'

# Exceptions: NeedsReview=true rows are listed as review exceptions; details still retain every row.
for out_r, ex in enumerate(exceptions, start=5):
    for c, v in enumerate(ex, start=1):
        cell = ws_ex.cell(out_r, c, v)
        cell.number_format = '@'

# Freeze panes / filters from template are retained if present. Apply autofilter ranges if template had only header dimensions.
ws_details.auto_filter.ref = f'A4:N{last_detail_row}'
last_summary_row = 4 + len(summary) if summary else 5
ws_summary.auto_filter.ref = f'A4:F{last_summary_row}'
last_ex_row = 4 + len(exceptions) if exceptions else 5
ws_ex.auto_filter.ref = f'A4:D{last_ex_row}'

wb.save(out_xlsx)
print('Wrote:', out_xlsx)
print('Details rows:', len(rows))
print('Summary rows:', len(summary))
print('NeedsReview true / Exceptions:', len(exceptions))

# Verification: reopen saved workbook and check stated requirements
wb2 = load_workbook(out_xlsx, data_only=False)
wd = wb2['Details']; ws = wb2['Summary']; we = wb2['Exceptions']
# Header check
if [wd.cell(4,c).value for c in range(1,15)] != expected:
    raise SystemExit('Saved Details headers changed')
# Row count check
actual_detail_rows = wd.max_row - 4
if actual_detail_rows != len(rows):
    raise SystemExit(f'Detail row count mismatch {actual_detail_rows} != {len(rows)}')
# Values/types/check computation and preservation
true_count = 0
for row_idx in range(5, wd.max_row+1):
    exp_id = wd.cell(row_idx,1).value
    emp_id = wd.cell(row_idx,2).value
    currency = wd.cell(row_idx,7).value
    amount_val = wd.cell(row_idx,8).value
    amount_twd_val = wd.cell(row_idx,9).value
    status = wd.cell(row_idx,10).value
    needs = wd.cell(row_idx,14).value
    if not isinstance(exp_id, str) or not isinstance(emp_id, str):
        raise SystemExit(f'ID not text at row {row_idx}')
    if not isinstance(amount_val, (int,float)) or not isinstance(amount_twd_val, (int,float)):
        raise SystemExit(f'Amount columns not numeric at row {row_idx}')
    calc = (Decimal(str(amount_val)) * rates[currency]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if Decimal(str(amount_twd_val)).quantize(Decimal('0.01')) != calc:
        raise SystemExit(f'AmountTWD mismatch at row {row_idx}: {amount_twd_val} != {calc}')
    expected_needs = 'true' if calc > Decimal('5000.00') else 'false'
    if needs != expected_needs:
        raise SystemExit(f'NeedsReview mismatch at row {row_idx}: {needs} != {expected_needs}')
    if status != 'Approved':
        raise SystemExit(f'Unexpected status at row {row_idx}: {status}')
    if needs == 'true': true_count += 1
# Summary check by recomputing from details and comparing rows
saved_summary = {}
for r in range(5, ws.max_row+1):
    key = (ws.cell(r,1).value, ws.cell(r,2).value, ws.cell(r,3).value)
    saved_summary[key] = (Decimal(str(ws.cell(r,4).value)).quantize(Decimal('0.01')), Decimal(str(ws.cell(r,5).value)).quantize(Decimal('0.01')), ws.cell(r,6).value)
expected_summary = {k: (v['amount'].quantize(Decimal('0.01')), v['twd'].quantize(Decimal('0.01')), v['count']) for k,v in summary.items()}
if saved_summary != expected_summary:
    raise SystemExit(f'Summary mismatch: {saved_summary} != {expected_summary}')
if ws['B2'].value != f'=SUM(Details!I5:I{last_detail_row})':
    raise SystemExit(f'Summary B2 formula unexpected: {ws["B2"].value}')
if we.max_row - 4 != true_count:
    raise SystemExit(f'Exceptions row count mismatch {we.max_row-4} != {true_count}')
print('Verified saved workbook: headers, 15 detail rows, text IDs, numeric Amount/AmountTWD, ROUND_HALF_UP FX conversion, NeedsReview flags, Summary grouping, B2 formula, Exceptions count.')
print('Output file:', out_xlsx.resolve())
