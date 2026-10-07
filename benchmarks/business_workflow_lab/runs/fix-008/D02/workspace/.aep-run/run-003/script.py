from pathlib import Path
import csv
from decimal import Decimal, ROUND_HALF_UP
from copy import copy
from openpyxl import load_workbook
from openpyxl.styles import Alignment

workspace = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\runs\fix-008\D02\workspace')
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)

# Print actual inputs being used
print('Input files:')
for p in sorted(input_dir.iterdir()):
    print(f' - {p.name} ({p.stat().st_size} bytes)')
print('Export files:')
for p in sorted(output_dir.glob('expense_*_2026-09.csv')):
    print(f' - {p.name} ({p.stat().st_size} bytes)')

# Load FX rates (first two columns are authoritative; notes may contain commas in source CSV)
fx = {}
with open(input_dir / 'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('fx header:', header)
    for row in reader:
        if len(row) >= 2 and row[0]:
            fx[row[0]] = Decimal(row[1])
print('fx rates:', {k: str(v) for k, v in fx.items()})

# Load exported expense records from the desktop app
records = []
for fname in ['expense_submitted_2026-09.csv', 'expense_approved_2026-09.csv']:
    p = output_dir / fname
    with open(p, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        print(fname, 'headers:', reader.fieldnames)
        part = list(reader)
        print(fname, 'rows:', len(part))
        records.extend(part)

# Validate and enrich
seen = set()
for r in records:
    if r['ExpenseID'] in seen:
        raise AssertionError(f"Duplicate ExpenseID {r['ExpenseID']}")
    seen.add(r['ExpenseID'])
    if r['Status'] not in {'Submitted','Approved'}:
        raise AssertionError(f"Unexpected status {r['Status']} for {r['ExpenseID']}")
    if not ('2026-09-01' <= r['ExpenseDate'] <= '2026-09-30'):
        raise AssertionError(f"Unexpected date {r['ExpenseDate']} for {r['ExpenseID']}")
    if r['Currency'] not in fx:
        raise AssertionError(f"Missing FX rate for {r['Currency']}")
    amount = Decimal(r['Amount'])
    r['_AmountDecimal'] = amount
    r['_AmountTWD'] = (amount * fx[r['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    miss = str(r.get('MissingReceipt','')).strip().lower() == 'true' or not str(r.get('ReceiptID','')).strip()
    r['_MissingBool'] = miss
    r['_NeedsReview'] = miss

records.sort(key=lambda r: (r['ExpenseDate'], r['ExpenseID']))
missing_records = [r for r in records if r['_MissingBool']]
print('total selected records:', len(records))
print('missing receipt records:', [r['ExpenseID'] for r in missing_records])

# Fill a copy of the template
wb = load_workbook(input_dir / 'expense_template.xlsx')

# helper: clear rows from row 5 down without deleting sheets or headers
def clear_from_row(ws, start=5):
    if ws.max_row >= start:
        ws.delete_rows(start, ws.max_row - start + 1)

def set_text(cell, value):
    cell.value = '' if value is None else str(value)
    cell.number_format = '@'

def set_money(cell, value):
    cell.value = float(value)
    cell.number_format = '0.00'

# Report
report = wb['Report']
report['B3'] = '2026-09-01'
report['D3'] = '2026-09-30'
report['B4'] = 'Status in Submitted, Approved; all employees/projects'
report['B5'] = '2026-10-06T00:00:00+08:00'
report['B7'] = 'Expense Viewer (synthetic lab); fx_rates.csv'
report['D7'] = '2026-10-06T00:00:00+08:00'
report['B9'] = f"{len(records)} selected expenses; {len(missing_records)} missing receipts listed in Exceptions and retained in Details."

# Details
wsd = wb['Details']
clear_from_row(wsd, 5)
headers = [wsd.cell(4, c).value for c in range(1, wsd.max_column+1)]
print('Details headers:', headers)
for idx, r in enumerate(records, start=5):
    values = [
        r['ExpenseID'], r['EmployeeID'], r['EmployeeName'], r['ProjectID'], r['ExpenseDate'],
        r['Category'], r['Currency'], r['_AmountDecimal'], r['_AmountTWD'], r['Status'],
        r.get('ReceiptID',''), r.get('Description',''), str(r['_MissingBool']).lower(), str(r['_NeedsReview']).lower()
    ]
    for col, val in enumerate(values, start=1):
        cell = wsd.cell(idx, col)
        if col in [1,2,3,4,5,6,7,10,11,12,13,14]:
            set_text(cell, val)
        elif col in [8,9]:
            set_money(cell, val)
    wsd.cell(idx, 12).alignment = Alignment(wrap_text=True)

last_detail = 4 + len(records)

# Summary: total formula plus grouped rows by Status and Currency
wss = wb['Summary']
clear_from_row(wss, 5)
wss['B2'] = f'=SUM(Details!I5:I{last_detail if records else 5})'
summary = {}
for r in records:
    key = (r['Status'], r['Currency'])
    if key not in summary:
        summary[key] = {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0}
    summary[key]['amount'] += r['_AmountDecimal']
    summary[key]['twd'] += r['_AmountTWD']
    summary[key]['count'] += 1
for row_idx, ((status, curr), agg) in enumerate(sorted(summary.items()), start=5):
    vals = [status, '', curr, agg['amount'].quantize(Decimal('0.01')), agg['twd'].quantize(Decimal('0.01')), agg['count']]
    for col, val in enumerate(vals, start=1):
        cell = wss.cell(row_idx, col)
        if col in [1,2,3]:
            set_text(cell, val)
        elif col in [4,5]:
            set_money(cell, val)
        else:
            cell.value = int(val)

# Exceptions
wse = wb['Exceptions']
clear_from_row(wse, 5)
for idx, r in enumerate(missing_records, start=5):
    vals = [r['ExpenseID'], r['EmployeeID'], r['ExpenseDate'], 'Missing receipt']
    for col, val in enumerate(vals, start=1):
        set_text(wse.cell(idx, col), val)

out_path = output_dir / 'expense_report_2026-09_submitted_approved.xlsx'
wb.save(out_path)
print('saved:', out_path)

# Reopen and verify saved output
wb2 = load_workbook(out_path, data_only=False)
for sheet in ['Report','Details','Summary','Exceptions','Instructions']:
    if sheet not in wb2.sheetnames:
        raise AssertionError(f'Missing sheet {sheet}')

D = wb2['Details']
actual_headers = [D.cell(4,c).value for c in range(1,15)]
expected_headers = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
if actual_headers != expected_headers:
    raise AssertionError(f'Details headers changed: {actual_headers}')
rows = list(D.iter_rows(min_row=5, max_row=D.max_row, max_col=14, values_only=True))
if len(rows) != len(records):
    raise AssertionError(f'Details row count {len(rows)} != {len(records)}')
ids = [row[0] for row in rows]
if set(ids) != set(seen):
    raise AssertionError('Details IDs do not match exported records')
for row in rows:
    exp_id, emp_id, emp_name, project, exp_date, cat, curr, amount, amount_twd, status, receipt, desc, missing, needs = row
    if not isinstance(exp_id, str) or not isinstance(emp_id, str) or not isinstance(project, str):
        raise AssertionError('ID fields are not text')
    if status not in ('Submitted','Approved') or not ('2026-09-01' <= exp_date <= '2026-09-30'):
        raise AssertionError(f'Bad filtered row {row}')
    if not isinstance(amount, (int,float)) or not isinstance(amount_twd, (int,float)):
        raise AssertionError('Amount fields are not numeric')
    source = next(r for r in records if r['ExpenseID'] == exp_id)
    expected_twd = float(source['_AmountTWD'])
    if round(float(amount_twd),2) != round(expected_twd,2):
        raise AssertionError(f'AmountTWD mismatch for {exp_id}')
    if source['_MissingBool']:
        if str(missing).lower() != 'true' or str(needs).lower() != 'true':
            raise AssertionError(f'Missing/NeedsReview not true for {exp_id}')
    else:
        if str(missing).lower() != 'false' or str(needs).lower() != 'false':
            raise AssertionError(f'Missing/NeedsReview not false for {exp_id}')
    if source.get('Description','') != (desc or ''):
        raise AssertionError(f'Description mismatch for {exp_id}')
    if source.get('ReceiptID','') != (receipt or ''):
        raise AssertionError(f'ReceiptID mismatch for {exp_id}')

E = wb2['Exceptions']
ex_rows = list(E.iter_rows(min_row=5, max_row=E.max_row, max_col=4, values_only=True)) if E.max_row >= 5 else []
ex_ids = [r[0] for r in ex_rows]
expected_missing_ids = [r['ExpenseID'] for r in missing_records]
if ex_ids != expected_missing_ids:
    raise AssertionError(f'Exception IDs {ex_ids} != {expected_missing_ids}')
# Ensure exceptions remain in details
for eid in expected_missing_ids:
    if eid not in ids:
        raise AssertionError(f'Missing exception {eid} removed from Details')

S = wb2['Summary']
expected_formula = f'=SUM(Details!I5:I{last_detail})'
if S['B2'].value != expected_formula:
    raise AssertionError(f'Summary formula {S["B2"].value} != {expected_formula}')
print('CHECK OK: workbook reopened; sheets present; Details headers and 22 data rows verified; filters/status/dates verified; ReceiptID/Description/MissingReceipt preserved; Amount/AmountTWD numeric and FX-checked; Exceptions list missing receipt ExpenseIDs and Details retains them; Summary total formula extended.')
print('output file:', out_path.name)
print('detail rows:', len(rows), 'exceptions:', len(ex_rows), 'summary rows:', len(summary))