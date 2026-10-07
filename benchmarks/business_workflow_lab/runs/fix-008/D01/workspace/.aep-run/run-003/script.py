from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from collections import defaultdict
import csv, re, sys

ws = Path.cwd()
input_dir = ws/'input'
out_dir = ws/'output'
out_dir.mkdir(exist_ok=True)
template_path = input_dir/'expense_template.xlsx'
fx_path = input_dir/'fx_rates.csv'
export_path = out_dir/'E001_2026-09_expense_export.xlsx'
output_path = out_dir/'E001_september_expenses.xlsx'

print('INPUTS')
for p in [template_path, fx_path, export_path]:
    print(p, 'exists=', p.exists(), 'size=', p.stat().st_size if p.exists() else None)

# Read FX rates. CSV has notes containing commas without quotes, so only first two columns matter.
fx = {}
with fx_path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('fx header', header)
    for row in reader:
        if not row or not row[0]:
            continue
        fx[row[0]] = Decimal(row[1])
print('fx rates', fx)

# Read export workbook
exp_wb = load_workbook(export_path, data_only=True)
exp_ws = exp_wb[exp_wb.sheetnames[0]]
headers = [c.value for c in exp_ws[1]]
print('export headers', headers)
required_export = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','Status','ReceiptID','Description','MissingReceipt']
missing = [h for h in required_export if h not in headers]
if missing:
    raise SystemExit(f'Missing export columns: {missing}')
idx = {h: headers.index(h)+1 for h in headers}
rows=[]
for r in range(2, exp_ws.max_row+1):
    rec={h: exp_ws.cell(r, idx[h]).value for h in required_export}
    if not rec['ExpenseID']:
        continue
    rows.append(rec)
print('export row count', len(rows))
print('sample rows', rows[:3])

# Helpers
def parse_date(v):
    if isinstance(v, datetime): return v.date()
    if isinstance(v, date): return v
    return datetime.strptime(str(v), '%Y-%m-%d').date()

def boolish(v):
    if isinstance(v, bool): return v
    if v is None: return False
    return str(v).strip().lower() in {'true','1','yes','y'}

def money(v):
    return Decimal(str(v)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def amount_twd(amount, currency):
    if currency not in fx:
        raise SystemExit(f'No FX rate for {currency}')
    return (money(amount) * fx[currency]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Fill a copy of template
wb = load_workbook(template_path)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']
exceptions = wb['Exceptions']

# Clear old data rows if any; preserve headers and formatting basics.
def clear_from(sheet, start_row):
    if sheet.max_row >= start_row:
        sheet.delete_rows(start_row, sheet.max_row-start_row+1)

clear_from(details, 5)
clear_from(summary, 5)
clear_from(exceptions, 5)

employee = 'E001'
from_date = '2026-09-01'
to_date = '2026-09-30'
generated_at = datetime.now().astimezone().isoformat(timespec='seconds')
report['B3'] = from_date
report['D3'] = to_date
report['B4'] = f'EmployeeID={employee}; ExpenseDate {from_date} to {to_date}; Status=All'
report['B5'] = generated_at
report['B7'] = 'Expense Viewer (synthetic lab) export'
report['D7'] = generated_at
report['B9'] = 'NeedsReview=true when MissingReceipt=true; Summary grouped by Status and Currency.'

summary_acc = defaultdict(lambda: {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0})
exceptions_rows=[]
for i, rec in enumerate(rows, start=5):
    d = parse_date(rec['ExpenseDate'])
    amt = money(rec['Amount'])
    twd = amount_twd(amt, rec['Currency'])
    missing_receipt = boolish(rec['MissingReceipt'])
    needs_review = missing_receipt
    values = [
        str(rec['ExpenseID']), str(rec['EmployeeID']), str(rec['EmployeeName']), str(rec['ProjectID']),
        d, str(rec['Category']), str(rec['Currency']), float(amt), float(twd), str(rec['Status']),
        None if rec['ReceiptID'] is None else str(rec['ReceiptID']), rec['Description'],
        'true' if missing_receipt else 'false', 'true' if needs_review else 'false'
    ]
    for col, val in enumerate(values, start=1):
        cell = details.cell(i, col, val)
    # Formats
    for col in [1,2,3,4,6,7,10,11,12,13,14]:
        details.cell(i, col).number_format = '@'
    details.cell(i, 5).number_format = 'yyyy-mm-dd'
    details.cell(i, 8).number_format = '0.00'
    details.cell(i, 9).number_format = '0.00'
    details.cell(i, 12).alignment = Alignment(wrap_text=True)
    key=(str(rec['Status']), str(rec['Currency']))
    summary_acc[key]['amount'] += amt
    summary_acc[key]['twd'] += twd
    summary_acc[key]['count'] += 1
    if needs_review:
        exceptions_rows.append([str(rec['ExpenseID']), str(rec['EmployeeID']), d, 'MissingReceipt=true; receipt is blank'])

# Summary rows grouped by Status and Currency
sr=5
for (status, currency), val in sorted(summary_acc.items(), key=lambda kv: (kv[0][0], kv[0][1])):
    summary.cell(sr,1,'Status')
    summary.cell(sr,2,status)
    summary.cell(sr,3,currency)
    summary.cell(sr,4,float(val['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)))
    summary.cell(sr,5,float(val['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)))
    summary.cell(sr,6,val['count'])
    summary.cell(sr,4).number_format='0.00'
    summary.cell(sr,5).number_format='0.00'
    sr+=1

last_detail_row = 4 + len(rows) if rows else 5
formula_last = 4 + len(rows) if rows else 5
summary['B2'] = f'=SUM(Details!I5:I{formula_last})'
summary['B2'].number_format = '0.00'

# Exceptions
for r, vals in enumerate(exceptions_rows, start=5):
    for c,val in enumerate(vals, start=1):
        exceptions.cell(r,c,val)
    exceptions.cell(r,1).number_format='@'
    exceptions.cell(r,2).number_format='@'
    exceptions.cell(r,3).number_format='yyyy-mm-dd'
    exceptions.cell(r,4).number_format='@'

# Save
wb.save(output_path)
print('saved', output_path)

# Verification from saved workbook
check_wb = load_workbook(output_path, data_only=False)
cd = check_wb['Details']; cs=check_wb['Summary']; ce=check_wb['Exceptions']; cr=check_wb['Report']
# row counts
actual_detail = sum(1 for r in range(5, cd.max_row+1) if cd.cell(r,1).value)
actual_summary = sum(1 for r in range(5, cs.max_row+1) if cs.cell(r,1).value)
actual_ex = sum(1 for r in range(5, ce.max_row+1) if ce.cell(r,1).value)
print('CHECK detail_rows', actual_detail)
print('CHECK summary_rows', actual_summary)
print('CHECK exception_rows', actual_ex)
print('CHECK output sheets', check_wb.sheetnames)
print('CHECK report B3 D3 B4', cr['B3'].value, cr['D3'].value, cr['B4'].value)
print('CHECK details headers', [cd.cell(4,c).value for c in range(1,15)])
print('CHECK summary headers', [cs.cell(4,c).value for c in range(1,7)])
print('CHECK summary B2 formula', cs['B2'].value)
# Calculate TWD total and compare formula range implied data
calc_total = Decimal('0.00')
for r in range(5, cd.max_row+1):
    if cd.cell(r,1).value:
        calc_total += Decimal(str(cd.cell(r,9).value)).quantize(Decimal('0.01'))
print('CHECK calculated_twd_total', calc_total)
# Confirm detail types/values
bad=[]
for r in range(5, cd.max_row+1):
    if not cd.cell(r,1).value: continue
    if not isinstance(cd.cell(r,1).value, str): bad.append((r,'ExpenseID not text'))
    if not isinstance(cd.cell(r,8).value, (int,float)): bad.append((r,'Amount not numeric'))
    if not isinstance(cd.cell(r,9).value, (int,float)): bad.append((r,'AmountTWD not numeric'))
    if cd.cell(r,13).value not in ('true','false'): bad.append((r,'MissingReceipt not true/false'))
    if cd.cell(r,14).value not in ('true','false'): bad.append((r,'NeedsReview not true/false'))
print('CHECK bad_cells', bad)
# Print summary values and export row count
for r in range(5, cs.max_row+1):
    if cs.cell(r,1).value:
        print('SUMMARY', [cs.cell(r,c).value for c in range(1,7)])
if actual_detail != len(rows): raise SystemExit('detail row count mismatch')
if bad: raise SystemExit(f'bad cells: {bad}')
print('VERIFIED OK')