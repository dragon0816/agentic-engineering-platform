from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import csv

wsdir = Path.cwd()
input_dir = wsdir/'input'
out_dir = wsdir/'output'
out_dir.mkdir(exist_ok=True)
export_path = out_dir/'expense_export_E001_2026-09.xlsx'
template_path = input_dir/'expense_template.xlsx'
fx_path = input_dir/'fx_rates.csv'
output_path = out_dir/'E001_september_expenses.xlsx'

print('Inputs:')
for p in [template_path, fx_path, export_path]:
    print(p.name, p.exists(), p.stat().st_size if p.exists() else None)

# Read FX rates (first two CSV fields only; notes may contain commas in source lab file)
rates = {}
with open(fx_path, newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('FX header:', header[:2])
    for row in reader:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('FX rates:', rates)

# Read exported expenses
src_wb = load_workbook(export_path, data_only=True)
src_ws = src_wb.active
headers = [c.value for c in src_ws[1]]
print('Export headers:', headers)
rows = []
for r in src_ws.iter_rows(min_row=2, values_only=True):
    if all(v is None for v in r):
        continue
    rec = dict(zip(headers, r))
    rows.append(rec)
print('Export row count:', len(rows))
print('Sample rows:', rows[:3])

# Helpers
def money(v):
    return Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def twd(amount, curr):
    if curr not in rates:
        raise ValueError(f'Missing FX rate for {curr}')
    return (money(amount) * rates[curr]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def truthy(v):
    if isinstance(v, bool): return v
    if v is None: return False
    return str(v).strip().lower() in {'true','1','yes','y'}

def copy_row_style(sh, src_row, dst_row, max_col):
    for col in range(1, max_col+1):
        src = sh.cell(src_row, col)
        dst = sh.cell(dst_row, col)
        if src.has_style:
            dst._style = copy(src._style)
        if src.number_format:
            dst.number_format = src.number_format
        if src.alignment:
            dst.alignment = copy(src.alignment)

# Load template
wb = load_workbook(template_path)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']
exceptions = wb['Exceptions']

# Report sheet
from_date = '2026-09-01'
to_date = '2026-09-30'
employee = 'E001'
generated_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
report['B3'] = from_date
report['D3'] = to_date
report['B4'] = f'EmployeeID={employee}; ExpenseDate {from_date} to {to_date}; all statuses'
report['B5'] = generated_at
report['B7'] = 'Expense Viewer (synthetic lab) export'
report['D7'] = generated_at
report['B9'] = 'NeedsReview=true when MissingReceipt=true. TWD amounts use input/fx_rates.csv fixed test rates.'

# Clear old data rows (if any), preserve row 4 header/template styles
for sh in [details, summary, exceptions]:
    if sh.max_row > 4:
        sh.delete_rows(5, sh.max_row-4)

# Details
for idx, rec in enumerate(rows, start=5):
    copy_row_style(details, 4, idx, 14)
    curr = rec['Currency']
    amt = money(rec['Amount'])
    amt_twd = twd(amt, curr)
    missing = truthy(rec.get('MissingReceipt'))
    needs_review = missing
    values = [
        rec.get('ExpenseID'), rec.get('EmployeeID'), rec.get('EmployeeName'), rec.get('ProjectID'),
        rec.get('ExpenseDate'), rec.get('Category'), curr, float(amt), float(amt_twd), rec.get('Status'),
        rec.get('ReceiptID'), rec.get('Description'), str(missing).lower(), str(needs_review).lower()
    ]
    for col, val in enumerate(values, start=1):
        cell = details.cell(idx, col, val)
        if col in [1,2,3,4,6,7,10,11,12,13,14]:
            cell.number_format = '@'
        elif col == 5:
            cell.number_format = 'yyyy-mm-dd'
        elif col in [8,9]:
            cell.number_format = '0.00'

last_detail = max(5, 4+len(rows))
summary['B2'] = f'=SUM(Details!I5:I{last_detail})'
summary['B2'].number_format = '0.00'

# Summary by status and currency
agg = {}
for rec in rows:
    key = (rec.get('Status'), rec.get('Currency'))
    amt = money(rec['Amount'])
    amt_twd = twd(amt, rec['Currency'])
    if key not in agg:
        agg[key] = {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0}
    agg[key]['amount'] += amt
    agg[key]['twd'] += amt_twd
    agg[key]['count'] += 1

for ridx, ((status, curr), data) in enumerate(sorted(agg.items()), start=5):
    copy_row_style(summary, 4, ridx, 6)
    vals = ['Status', status, curr, float(data['amount'].quantize(Decimal('0.01'))), float(data['twd'].quantize(Decimal('0.01'))), data['count']]
    for col, val in enumerate(vals, start=1):
        summary.cell(ridx, col, val)
    summary.cell(ridx,4).number_format = '0.00'
    summary.cell(ridx,5).number_format = '0.00'

# Exceptions for missing receipt / data issues
ex_rows=[]
for rec in rows:
    reasons=[]
    if truthy(rec.get('MissingReceipt')):
        reasons.append('MissingReceipt=true')
    if not rec.get('ReceiptID'):
        reasons.append('ReceiptID blank')
    if rec.get('Currency') not in rates:
        reasons.append(f"Missing FX rate for {rec.get('Currency')}")
    if reasons:
        ex_rows.append((rec.get('ExpenseID'), rec.get('EmployeeID'), rec.get('ExpenseDate'), '; '.join(reasons)))
for ridx, vals in enumerate(ex_rows, start=5):
    copy_row_style(exceptions, 4, ridx, 4)
    for col, val in enumerate(vals, start=1):
        exceptions.cell(ridx, col, val)
        if col in [1,2,4]: exceptions.cell(ridx, col).number_format='@'
        if col == 3: exceptions.cell(ridx, col).number_format='yyyy-mm-dd'

# Freeze/filter as available, no layout changes. Save
wb.save(output_path)
print('Wrote', output_path)
print('Summary rows:')
for row in summary.iter_rows(min_row=5, max_row=summary.max_row, values_only=True):
    print(row)
print('Exceptions:', len(ex_rows), ex_rows)

# Verification reopen saved output
check = load_workbook(output_path, data_only=False)
print('\nVERIFY')
print('Sheets:', check.sheetnames)
assert check.sheetnames == ['Report', 'Details', 'Summary', 'Exceptions', 'Instructions']
cd = check['Details']; cs = check['Summary']; ce = check['Exceptions']; cr = check['Report']
expected_headers = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
actual_headers = [cd.cell(4,c).value for c in range(1,15)]
print('Details headers:', actual_headers)
assert actual_headers == expected_headers
assert cd.max_row == 17, cd.max_row
assert all(cd.cell(r,2).value == 'E001' for r in range(5,18))
assert all(str(cd.cell(r,5).value)[:10] >= from_date and str(cd.cell(r,5).value)[:10] <= to_date for r in range(5,18))
# Numeric amount checks
for r in range(5,18):
    assert isinstance(cd.cell(r,8).value, (int,float))
    assert isinstance(cd.cell(r,9).value, (int,float))
# Summary status+currency verification
summary_rows = [[cs.cell(r,c).value for c in range(1,7)] for r in range(5, cs.max_row+1)]
print('Summary B2 formula:', cs['B2'].value)
print('Summary rows count:', len(summary_rows))
assert cs['B2'].value == '=SUM(Details!I5:I17)'
assert summary_rows
# Calculate TWD total from saved detail cells
total_twd = sum(Decimal(str(cd.cell(r,9).value)) for r in range(5,18)).quantize(Decimal('0.01'))
summary_twd = sum(Decimal(str(row[4])) for row in summary_rows).quantize(Decimal('0.01'))
print('TWD total from Details:', total_twd)
print('TWD total from Summary rows:', summary_twd)
assert total_twd == summary_twd
print('Exceptions rows:', max(0, ce.max_row-4))
print('Output file:', output_path.name, 'bytes', output_path.stat().st_size)