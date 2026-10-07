from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Alignment, Protection
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
import csv, json, shutil

base=Path.cwd()
input_dir=base/'input'
output_dir=base/'output'
output_dir.mkdir(exist_ok=True)
template=input_dir/'expense_template.xlsx'
export=output_dir/'expense_export_E001_2026-09.xlsx'
out=output_dir/'E001_september_expenses.xlsx'

# print actual inputs
print('Inputs:')
for p in sorted(input_dir.glob('*')): print('-', p.name, p.stat().st_size)
print('Export:', export, export.exists(), export.stat().st_size if export.exists() else None)

# Read FX rates. Note field may contain commas; only first two columns matter.
rates={}
with (input_dir/'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    reader=csv.DictReader(f)
    print('FX headers:', reader.fieldnames)
    for row in reader:
        if row.get('Currency'):
            rates[row['Currency']]=Decimal(str(row['RateToTWD']))
print('FX rates:', rates)

# Read export
src_wb=load_workbook(export, data_only=True)
src_ws=src_wb.active
headers=[c.value for c in src_ws[1]]
print('Export headers:', headers)
rows=[]
for vals in src_ws.iter_rows(min_row=2, values_only=True):
    if not any(v is not None for v in vals):
        continue
    rec=dict(zip(headers, vals))
    rows.append(rec)
print('Export row count:', len(rows))
print('First rows:', json.dumps(rows[:3], ensure_ascii=False, default=str))

# Helpers
def q2(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def copy_row_style(ws, src_row, dst_row, max_col):
    for col in range(1, max_col+1):
        src=ws.cell(src_row, col)
        dst=ws.cell(dst_row, col)
        if src.has_style:
            dst._style = src._style.copy()
        if src.number_format:
            dst.number_format = src.number_format
        if src.alignment:
            dst.alignment = src.alignment.copy()

# Open template copy in memory
wb=load_workbook(template)
report=wb['Report']; details=wb['Details']; summary=wb['Summary']; exceptions=wb['Exceptions']

from_date='2026-09-01'; to_date='2026-09-30'; employee='E001'
taipei=timezone(timedelta(hours=8))
now=datetime.now(taipei).replace(microsecond=0).isoformat()

# Clear old data rows preserving row 4 header and basic style from row 5 if any
for ws in (details, summary, exceptions):
    if ws.max_row > 4:
        ws.delete_rows(5, ws.max_row-4)

# Report fields
report['B3']=from_date
report['D3']=to_date
report['B4']=f'EmployeeID={employee}; ExpenseDate {from_date} to {to_date}; Status=ALL'
report['B5']=now
report['B7']='Expense Viewer (synthetic lab) Export Excel'
report['D7']=now
report['B9']='All exported rows included. NeedsReview/Exceptions mark MissingReceipt=true from source export. AmountTWD uses input/fx_rates.csv fixed test rates.'

# Detail rows
last_detail_row=4
exceptions_out=[]
summary_map={}
for idx, rec in enumerate(rows, start=5):
    if idx > 5:
        copy_row_style(details, 5, idx, 14)
    cur=str(rec.get('Currency') or '')
    amt=q2(rec.get('Amount') or '0')
    if cur not in rates:
        raise ValueError(f'Missing FX rate for {cur}')
    amt_twd=q2(amt * rates[cur])
    missing=rec.get('MissingReceipt')
    missing_bool = bool(missing) if isinstance(missing, bool) else str(missing).strip().lower() in ('true','1','yes','y')
    needs_review=missing_bool
    values=[
        rec.get('ExpenseID'), rec.get('EmployeeID'), rec.get('EmployeeName'), rec.get('ProjectID'), rec.get('ExpenseDate'),
        rec.get('Category'), cur, float(amt), float(amt_twd), rec.get('Status'), rec.get('ReceiptID'), rec.get('Description'),
        str(missing_bool).lower(), str(needs_review).lower()
    ]
    for col, val in enumerate(values, start=1):
        c=details.cell(idx, col)
        c.value=val
    # formats
    for col in [1,2,3,4,6,7,10,11,12,13,14]:
        details.cell(idx,col).number_format='@'
    details.cell(idx,5).number_format='yyyy-mm-dd'
    details.cell(idx,8).number_format='0.00'
    details.cell(idx,9).number_format='0.00'
    key=(str(rec.get('Status') or ''), cur)
    if key not in summary_map:
        summary_map[key]={'amount':Decimal('0'), 'amount_twd':Decimal('0'), 'count':0}
    summary_map[key]['amount']+=amt
    summary_map[key]['amount_twd']+=amt_twd
    summary_map[key]['count']+=1
    if missing_bool:
        exceptions_out.append((rec.get('ExpenseID'), rec.get('EmployeeID'), rec.get('ExpenseDate'), 'MissingReceipt=true'))
    last_detail_row=idx

# Summary formula and rows
if rows:
    summary['B2']=f'=SUM(Details!I5:I{last_detail_row})'
else:
    summary['B2']='=SUM(Details!I5:I5)'
summary['B2'].number_format='0.00'

for r_idx, ((status, cur), vals) in enumerate(sorted(summary_map.items()), start=5):
    if r_idx > 5:
        copy_row_style(summary, 5, r_idx, 6)
    summary.cell(r_idx,1).value='Status'
    summary.cell(r_idx,2).value=status
    summary.cell(r_idx,3).value=cur
    summary.cell(r_idx,4).value=float(q2(vals['amount']))
    summary.cell(r_idx,5).value=float(q2(vals['amount_twd']))
    summary.cell(r_idx,6).value=vals['count']
    summary.cell(r_idx,4).number_format='0.00'
    summary.cell(r_idx,5).number_format='0.00'
# Add explicit grand TWD total row for readability without changing B2 formula
r_total=5+len(summary_map)
if r_total > 5:
    copy_row_style(summary, 5, r_total, 6)
summary.cell(r_total,1).value='GrandTotal'
summary.cell(r_total,2).value='TWD total'
summary.cell(r_total,3).value='TWD'
summary.cell(r_total,4).value=None
summary.cell(r_total,5).value=f'=B2'
summary.cell(r_total,6).value=len(rows)
summary.cell(r_total,5).number_format='0.00'

# Exceptions
for r_idx, vals in enumerate(exceptions_out, start=5):
    if r_idx > 5:
        copy_row_style(exceptions, 5, r_idx, 4)
    for col, val in enumerate(vals, start=1):
        exceptions.cell(r_idx,col).value=val
    for col in [1,2,4]: exceptions.cell(r_idx,col).number_format='@'
    exceptions.cell(r_idx,3).number_format='yyyy-mm-dd'

# Ensure output file
wb.save(out)
print('Wrote', out, out.stat().st_size)

# Reopen and validate requirements from saved output
check=load_workbook(out, data_only=False)
assert check.sheetnames == ['Report', 'Details', 'Summary', 'Exceptions', 'Instructions']
d=check['Details']; s=check['Summary']; e=check['Exceptions']; r=check['Report']
expected_detail_headers=['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
actual_headers=[d.cell(4,c).value for c in range(1,15)]
assert actual_headers==expected_detail_headers, actual_headers
# Count rows nonempty
n=sum(1 for rr in range(5,d.max_row+1) if d.cell(rr,1).value)
assert n==len(rows)==13, (n,len(rows))
assert r['B3'].value==from_date and r['D3'].value==to_date
# IDs are strings, Amount and AmountTWD numeric
for rr in range(5,5+n):
    assert isinstance(d.cell(rr,1).value, str)
    assert isinstance(d.cell(rr,2).value, str)
    assert isinstance(d.cell(rr,8).value, (int,float))
    assert isinstance(d.cell(rr,9).value, (int,float))
# Summary status+currency totals recompute
saved_total=Decimal('0')
for rr in range(5,5+n):
    saved_total += Decimal(str(d.cell(rr,9).value)).quantize(Decimal('0.01'))
print('Validated detail rows:', n)
print('Summary B2 formula:', s['B2'].value)
print('Calculated TWD total from Details:', saved_total)
print('Exceptions rows:', sum(1 for rr in range(5,e.max_row+1) if e.cell(rr,1).value))
print('Summary rows:')
for rr in range(5, s.max_row+1):
    if s.cell(rr,1).value:
        print([s.cell(rr,c).value for c in range(1,7)])
