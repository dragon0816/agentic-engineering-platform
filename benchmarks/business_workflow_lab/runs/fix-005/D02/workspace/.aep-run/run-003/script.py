from pathlib import Path
import csv
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from collections import defaultdict
from openpyxl import load_workbook
from openpyxl.styles import Font

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)

TEMPLATE = input_dir / 'expense_template.xlsx'
FX = input_dir / 'fx_rates.csv'
CSV_FILES = [output_dir / 'expense_submitted_2026_09.csv', output_dir / 'expense_approved_2026_09.csv']
OUT = output_dir / 'expense_report_2026_09_submitted_approved.xlsx'

START = '2026-09-01'
END = '2026-09-30'
STATUSES = {'Submitted', 'Approved'}

TWOPLACES = Decimal('0.01')
def money(x):
    return Decimal(str(x)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

# Load FX rates. CSV notes contain commas in unquoted text in this fixture; first two columns are authoritative.
rates = {}
with open(FX, newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row or len(row) < 2:
            continue
        rates[row[0]] = Decimal(row[1])
print('FX rates loaded:', rates)

# Read exported rows from desktop Expense Viewer.
rows = []
seen = set()
for path in CSV_FILES:
    print('Reading', path.name)
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        print(' headers:', reader.fieldnames)
        for r in reader:
            exp_id = r['ExpenseID']
            if exp_id in seen:
                raise ValueError(f'Duplicate ExpenseID in exports: {exp_id}')
            seen.add(exp_id)
            if not (START <= r['ExpenseDate'] <= END):
                raise ValueError(f'Out-of-period row: {exp_id} {r["ExpenseDate"]}')
            if r['Status'] not in STATUSES:
                raise ValueError(f'Unexpected status: {exp_id} {r["Status"]}')
            if r['Currency'] not in rates:
                raise ValueError(f'Missing FX rate for {r["Currency"]}')
            amount = Decimal(r['Amount'])
            amount_twd = (amount * rates[r['Currency']]).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
            missing = str(r.get('MissingReceipt','')).strip().lower() == 'true'
            rows.append({
                'ExpenseID': r['ExpenseID'],
                'EmployeeID': r['EmployeeID'],
                'EmployeeName': r['EmployeeName'],
                'ProjectID': r['ProjectID'],
                'ExpenseDate': datetime.strptime(r['ExpenseDate'], '%Y-%m-%d').date(),
                'Category': r['Category'],
                'Currency': r['Currency'],
                'Amount': amount,
                'AmountTWD': amount_twd,
                'Status': r['Status'],
                'ReceiptID': r.get('ReceiptID',''),
                'Description': r.get('Description',''),
                'MissingReceipt': 'true' if missing else 'false',
                'NeedsReview': 'true' if missing else 'false',
                '_missing_bool': missing,
            })
rows.sort(key=lambda x: (x['ExpenseDate'], x['ExpenseID']))
print('Rows collected:', len(rows))
print('Missing receipt IDs:', [r['ExpenseID'] for r in rows if r['_missing_bool']])

wb = load_workbook(TEMPLATE)

# Helper to clear old data below header while preserving row 4 header and sheet structure.
def clear_rows(ws, start_row, max_col):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)
    # Ensure the row immediately below header exists for zero-row formulas/style anchors if needed.

# Report sheet
report = wb['Report']
report['B3'] = START
report['D3'] = END
report['B4'] = 'ExpenseDate 2026-09-01 to 2026-09-30; Status in Submitted, Approved'
now = datetime.now().astimezone().replace(microsecond=0).isoformat()
report['B5'] = now
report['B7'] = 'Expense Viewer (synthetic lab); fx_rates.csv'
report['D7'] = now
missing_count = sum(1 for r in rows if r['_missing_bool'])
report['B9'] = f'{len(rows)} expenses included. {missing_count} missing receipt expense(s) listed in Exceptions and retained in Details.'

# Details
wsd = wb['Details']
clear_rows(wsd, 5, 14)
headers = [wsd.cell(4, c).value for c in range(1, 15)]
expected_headers = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
if headers != expected_headers:
    raise ValueError(f'Details headers changed/unexpected: {headers}')
for idx, r in enumerate(rows, 5):
    vals = [r[h] for h in expected_headers]
    for c, val in enumerate(vals, 1):
        cell = wsd.cell(idx, c, val)
        if c in [1,2,4,11,13,14]:
            cell.number_format = '@'
        elif c == 5:
            cell.number_format = 'yyyy-mm-dd'
        elif c in [8,9]:
            cell.value = float(val)
            cell.number_format = '0.00'
    # Make multi-line descriptions visible without changing layout.
    wsd.cell(idx, 12).alignment = wsd.cell(idx, 12).alignment.copy(wrap_text=True)

# Summary: total formula and per Status/Currency aggregation without mixing original currencies.
wss = wb['Summary']
clear_rows(wss, 5, 6)
last_details_row = 4 + len(rows) if rows else 5
if rows:
    wss['B2'] = f'=SUM(Details!I5:I{last_details_row})'
else:
    wss['B2'] = '=SUM(Details!I5:I5)'
summary = defaultdict(lambda: {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
for r in rows:
    key = (r['Status'], r['Currency'])
    summary[key]['amount'] += r['Amount']
    summary[key]['twd'] += r['AmountTWD']
    summary[key]['count'] += 1
for ridx, ((status, curr), agg) in enumerate(sorted(summary.items()), 5):
    wss.cell(ridx, 1, 'Status')
    wss.cell(ridx, 2, status)
    wss.cell(ridx, 3, curr)
    wss.cell(ridx, 4, float(agg['amount'].quantize(TWOPLACES, rounding=ROUND_HALF_UP)))
    wss.cell(ridx, 5, float(agg['twd'].quantize(TWOPLACES, rounding=ROUND_HALF_UP)))
    wss.cell(ridx, 6, agg['count'])
    wss.cell(ridx, 4).number_format = '0.00'
    wss.cell(ridx, 5).number_format = '0.00'

# Exceptions: missing receipt only, retaining original ExpenseID and Details rows.
wse = wb['Exceptions']
clear_rows(wse, 5, 4)
exception_rows = [r for r in rows if r['_missing_bool']]
for ridx, r in enumerate(exception_rows, 5):
    wse.cell(ridx, 1, r['ExpenseID']).number_format = '@'
    wse.cell(ridx, 2, r['EmployeeID']).number_format = '@'
    wse.cell(ridx, 3, r['ExpenseDate']).number_format = 'yyyy-mm-dd'
    wse.cell(ridx, 4, 'Missing receipt')

# Save
wb.save(OUT)
print('Wrote', OUT)

# Reopen and validate all stated requirements from saved output.
wb2 = load_workbook(OUT, data_only=False)
assert wb2.sheetnames == ['Report', 'Details', 'Summary', 'Exceptions', 'Instructions']
d = wb2['Details']
e = wb2['Exceptions']
s = wb2['Summary']
# Headers preserved
assert [d.cell(4,c).value for c in range(1,15)] == expected_headers
assert [e.cell(4,c).value for c in range(1,5)] == ['ExpenseID','EmployeeID','ExpenseDate','Reason']
# Row counts
saved_detail_ids = [d.cell(r,1).value for r in range(5, d.max_row+1) if d.cell(r,1).value]
assert len(saved_detail_ids) == len(rows), (len(saved_detail_ids), len(rows))
assert set(saved_detail_ids) == {r['ExpenseID'] for r in rows}
# Date/status filters and detail fields
for r in range(5, d.max_row+1):
    if not d.cell(r,1).value:
        continue
    exp_id = d.cell(r,1).value
    expense_date = d.cell(r,5).value
    if isinstance(expense_date, datetime):
        expense_date = expense_date.date()
    assert date(2026,9,1) <= expense_date <= date(2026,9,30), (exp_id, expense_date)
    assert d.cell(r,10).value in STATUSES, (exp_id, d.cell(r,10).value)
    assert isinstance(d.cell(r,8).value, (int, float)), exp_id
    assert isinstance(d.cell(r,9).value, (int, float)), exp_id
    assert d.cell(r,13).value in ('true','false'), (exp_id, d.cell(r,13).value)
    assert d.cell(r,14).value in ('true','false'), (exp_id, d.cell(r,14).value)
# Exceptions equal missing receipts and missing records retained in Details
saved_exception_ids = [e.cell(r,1).value for r in range(5, e.max_row+1) if e.cell(r,1).value]
expected_exception_ids = [r['ExpenseID'] for r in rows if r['_missing_bool']]
assert saved_exception_ids == expected_exception_ids, (saved_exception_ids, expected_exception_ids)
for exp_id in saved_exception_ids:
    assert exp_id in saved_detail_ids
# Summary total formula and aggregation count
expected_formula = f'=SUM(Details!I5:I{4+len(rows)})' if rows else '=SUM(Details!I5:I5)'
assert s['B2'].value == expected_formula, (s['B2'].value, expected_formula)
summary_count = sum(s.cell(r,6).value or 0 for r in range(5, s.max_row+1))
assert summary_count == len(rows), summary_count
print('Validation OK')
print(' detail rows:', len(saved_detail_ids))
print(' exception rows:', len(saved_exception_ids), saved_exception_ids)
print(' summary formula:', s['B2'].value)
print(' output:', OUT.relative_to(workspace))
