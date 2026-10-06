from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
import csv, shutil

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)

template = input_dir / 'expense_template.xlsx'
fx_file = input_dir / 'fx_rates.csv'
export_file = output_dir / 'E001_september_export.xlsx'
out_file = output_dir / 'E001_september_expenses.xlsx'

employee_id = 'E001'
date_from = '2026-09-01'
date_to = '2026-09-30'
source_name = 'Expense Viewer (synthetic lab) export'

def q2(value):
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

print('Inputs:')
for p in [template, fx_file, export_file]:
    print(f' - {p}: exists={p.exists()} size={p.stat().st_size if p.exists() else None}')

# Read FX rates (first two columns; Note text contains commas in this synthetic file).
rates = {}
with fx_file.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('fx header:', header)
    for row in reader:
        if not row or not row[0].strip():
            continue
        rates[row[0].strip()] = Decimal(row[1].strip())
print('rates:', rates)

# Read exported data.
exp_wb = load_workbook(export_file, read_only=True, data_only=True)
exp_ws = exp_wb[exp_wb.sheetnames[0]]
headers = [c.value for c in exp_ws[1]]
print('export headers:', headers)
records = []
for row in exp_ws.iter_rows(min_row=2, values_only=True):
    if all(v is None for v in row):
        continue
    rec = dict(zip(headers, row))
    records.append(rec)
print('export row count:', len(records))
print('first rows:', records[:3])

# Validate export matches request.
for rec in records:
    if str(rec['EmployeeID']) != employee_id:
        raise AssertionError(f"Unexpected EmployeeID {rec['EmployeeID']} in {rec['ExpenseID']}")
    d = str(rec['ExpenseDate'])[:10]
    if not (date_from <= d <= date_to):
        raise AssertionError(f"Unexpected ExpenseDate {d} in {rec['ExpenseID']}")
    if rec['Currency'] not in rates:
        raise AssertionError(f"Missing FX rate for {rec['Currency']}")

# Prepare workbook from template.
shutil.copyfile(template, out_file)
wb = load_workbook(out_file)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']
exceptions = wb['Exceptions']

# Clear existing data rows but keep row 4 headers/sheets/formulas elsewhere.
def clear_rows(ws, min_row, max_col):
    for row in ws.iter_rows(min_row=min_row, max_row=ws.max_row, min_col=1, max_col=max_col):
        for cell in row:
            cell.value = None

clear_rows(details, 5, 14)
clear_rows(summary, 5, 6)
clear_rows(exceptions, 5, 4)

# Metadata.
taipei = timezone(timedelta(hours=8))
now = datetime.now(taipei).replace(microsecond=0).isoformat()
report['B3'] = date_from
report['D3'] = date_to
report['B4'] = f'EmployeeID={employee_id}; ExpenseDate {date_from} to {date_to}; Status=ALL; Project=ALL'
report['B5'] = now
report['B7'] = source_name
report['D7'] = now

# Details.
detail_headers = [details.cell(row=4, column=col).value for col in range(1, 15)]
print('detail template headers:', detail_headers)
summary_map = {}
exception_rows = []
for idx, rec in enumerate(records, start=5):
    amount = q2(rec['Amount'])
    rate = rates[str(rec['Currency'])]
    amount_twd = (amount * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    missing = bool(rec.get('MissingReceipt'))
    status = str(rec.get('Status') or '')
    needs_review = missing or status in {'Draft', 'Rejected'}
    values = [
        str(rec.get('ExpenseID') or ''),
        str(rec.get('EmployeeID') or ''),
        str(rec.get('EmployeeName') or ''),
        str(rec.get('ProjectID') or ''),
        str(rec.get('ExpenseDate') or '')[:10],
        str(rec.get('Category') or ''),
        str(rec.get('Currency') or ''),
        float(amount),
        float(amount_twd),
        status,
        '' if rec.get('ReceiptID') is None else str(rec.get('ReceiptID')),
        '' if rec.get('Description') is None else str(rec.get('Description')),
        'true' if missing else 'false',
        'true' if needs_review else 'false',
    ]
    for col, val in enumerate(values, start=1):
        c = details.cell(row=idx, column=col, value=val)
        if col in [1,2,3,4,5,6,7,10,11,12,13,14]:
            c.number_format = '@'
        if col in [8,9]:
            c.number_format = '0.00'
        if col == 12:
            c.alignment = Alignment(wrap_text=True)
    key = (status, str(rec['Currency']))
    agg = summary_map.setdefault(key, {'amount': Decimal('0.00'), 'amount_twd': Decimal('0.00'), 'count': 0})
    agg['amount'] += amount
    agg['amount_twd'] += amount_twd
    agg['count'] += 1
    reasons = []
    if missing:
        reasons.append('Missing receipt')
    if status == 'Draft':
        reasons.append('Draft status')
    if status == 'Rejected':
        reasons.append('Rejected status')
    if reasons:
        exception_rows.append([str(rec.get('ExpenseID') or ''), str(rec.get('EmployeeID') or ''), str(rec.get('ExpenseDate') or '')[:10], '; '.join(reasons)])

last_detail_row = 4 + len(records) if records else 5
summary['B2'] = f'=SUM(Details!I5:I{last_detail_row if records else 5})'
# Summary rows sorted by Status then Currency.
for r, ((status, currency), agg) in enumerate(sorted(summary_map.items()), start=5):
    vals = ['Status', status, currency, float(q2(agg['amount'])), float(q2(agg['amount_twd'])), int(agg['count'])]
    for col, val in enumerate(vals, start=1):
        c = summary.cell(row=r, column=col, value=val)
        if col in [4,5]:
            c.number_format = '0.00'

for r, vals in enumerate(exception_rows, start=5):
    for col, val in enumerate(vals, start=1):
        exceptions.cell(row=r, column=col, value=val)

total_twd = sum((q2(rec['Amount']) * rates[str(rec['Currency'])]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP) for rec in records)
report['B9'] = f'Exported {len(records)} expenses. Total TWD={total_twd}. NeedsReview flags: missing receipt, Draft, or Rejected.'

wb.save(out_file)
print('saved:', out_file)

# Verification: reopen saved output and check stated requirements.
check_wb_formula = load_workbook(out_file, data_only=False)
check_wb_values = load_workbook(out_file, data_only=True)
cd = check_wb_values['Details']
cs = check_wb_values['Summary']
cr = check_wb_values['Report']
# Count detail rows with an ExpenseID.
detail_ids = [cd.cell(row=r, column=1).value for r in range(5, cd.max_row + 1) if cd.cell(row=r, column=1).value]
if len(detail_ids) != len(records):
    raise AssertionError(f'Detail row count {len(detail_ids)} != exported records {len(records)}')
if len(records) != 13:
    raise AssertionError(f'Expected 13 records from app query, got {len(records)}')
# Check headers preserved.
expected_detail_headers = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
actual_detail_headers = [cd.cell(row=4, column=c).value for c in range(1,15)]
if actual_detail_headers != expected_detail_headers:
    raise AssertionError(f'Detail headers changed: {actual_detail_headers}')
# Check value types/formats and date range.
calc_total = Decimal('0.00')
for r in range(5, 5+len(records)):
    emp = cd.cell(r,2).value
    d = cd.cell(r,5).value
    amt = cd.cell(r,8).value
    twd = cd.cell(r,9).value
    miss = cd.cell(r,13).value
    review = cd.cell(r,14).value
    if emp != employee_id or not (date_from <= str(d) <= date_to):
        raise AssertionError(f'Bad filter row {r}: {emp}, {d}')
    if not isinstance(amt, (int,float)) or not isinstance(twd, (int,float)):
        raise AssertionError(f'Amounts not numeric row {r}: {amt!r}, {twd!r}')
    if str(miss).lower() not in ['true','false'] or str(review).lower() not in ['true','false']:
        raise AssertionError(f'Boolean text invalid row {r}: {miss!r}, {review!r}')
    calc_total += Decimal(str(twd)).quantize(Decimal('0.01'))
formula = check_wb_formula['Summary']['B2'].value
expected_formula = '=SUM(Details!I5:I17)'
if formula != expected_formula:
    raise AssertionError(f'Unexpected Summary!B2 formula {formula}, expected {expected_formula}')
# Summary rows count and totals.
summary_rows = [(cs.cell(r,1).value, cs.cell(r,2).value, cs.cell(r,3).value, cs.cell(r,4).value, cs.cell(r,5).value, cs.cell(r,6).value) for r in range(5, cs.max_row+1) if cs.cell(r,1).value]
if len(summary_rows) != len(summary_map):
    raise AssertionError('Summary row count mismatch')
summary_total = sum(Decimal(str(row[4])).quantize(Decimal('0.01')) for row in summary_rows)
if summary_total != calc_total:
    raise AssertionError(f'Summary TWD total {summary_total} != details total {calc_total}')
exception_count = len([exceptions.cell(r,1).value for r in range(5, exceptions.max_row+1) if exceptions.cell(r,1).value])
print('Verification passed:')
print(' - output file exists:', out_file.name, out_file.stat().st_size, 'bytes')
print(' - Details row count:', len(detail_ids))
print(' - Details headers preserved:', actual_detail_headers)
print(' - Filters checked: EmployeeID', employee_id, 'dates', date_from, 'to', date_to)
print(' - Amount and AmountTWD numeric with two-decimal format; ID/date/status fields text')
print(' - MissingReceipt/NeedsReview values are true/false')
print(' - Summary rows by Status and Currency:', summary_rows)
print(' - Summary!B2 formula:', formula)
print(' - Total TWD from saved detail rows:', calc_total)
print(' - Exception rows:', exception_count)
print(' - Report note:', cr['B9'].value)