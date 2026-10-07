import csv, shutil, os, re
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from openpyxl import load_workbook
from openpyxl.styles import Font
import json

params=json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))
employee=str(params.get('employee_id','')).strip()
q_from=str(params.get('date_from','')).strip()
q_to=str(params.get('date_to','')).strip()
output_filename=str(params.get('output_filename') or '').strip()
if not employee or not q_from or not q_to:
    raise ValueError('employee_id, date_from, and date_to are required')
if q_from > q_to:
    raise ValueError('date_from must be on or before date_to')
if not output_filename:
    safe_emp=re.sub(r'[^A-Za-z0-9_-]+','_',employee)
    output_filename=f'{safe_emp}_{q_from}_{q_to}_expenses.xlsx'
if not output_filename.lower().endswith('.xlsx'):
    output_filename += '.xlsx'
if Path(output_filename).name != output_filename:
    raise ValueError('output_filename must be a file name, not a path')

workspace=Path.cwd()
input_dir=workspace/'input'
output_dir=workspace/'output'
output_dir.mkdir(exist_ok=True)
export_csv=output_dir/f'expense_export_{employee}_{q_from}_{q_to}.csv'
template=input_dir/'expense_template.xlsx'
fx_file=input_dir/'fx_rates.csv'
outfile=output_dir/output_filename

print('Inputs:')
print(' export_csv', export_csv, export_csv.exists(), export_csv.stat().st_size if export_csv.exists() else None)
print(' template', template, template.exists(), template.stat().st_size if template.exists() else None)
print(' fx_file', fx_file, fx_file.exists(), fx_file.stat().st_size if fx_file.exists() else None)

rates={}
with open(fx_file, newline='', encoding='utf-8-sig') as f:
    reader=csv.reader(f)
    header=next(reader)
    print('fx header:', header)
    for row in reader:
        if len(row)>=2 and row[0]:
            rates[row[0]]=Decimal(row[1])
print('rates:', rates)

with open(export_csv, newline='', encoding='utf-8-sig') as f:
    reader=csv.DictReader(f)
    rows=list(reader)
    fields=reader.fieldnames or []
print('export header:', fields)
print('export row count:', len(rows))
print('sample rows:', rows[:2])
required=['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','Status','ReceiptID','Description','MissingReceipt']
missing=[c for c in required if c not in fields]
if missing:
    raise ValueError(f'export is missing columns: {missing}')
bad=[r for r in rows if r['EmployeeID']!=employee or not(q_from <= r['ExpenseDate'] <= q_to)]
if bad:
    raise ValueError(f'Export contains {len(bad)} rows outside requested employee/date range, e.g. {bad[:2]}')

shutil.copyfile(template, outfile)
wb=load_workbook(outfile)
for sheet_name in ['Details','Summary','Exceptions']:
    ws=wb[sheet_name]
    if ws.max_row>=5:
        for row in ws.iter_rows(min_row=5, max_row=ws.max_row):
            for cell in row:
                cell.value=None

now=datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
ws=wb['Report']
ws['B3']=q_from
ws['D3']=q_to
ws['B4']=f'EmployeeID={employee}; ExpenseDate {q_from} to {q_to}; Status=all'
ws['B5']=now
ws['B7']='Expense Viewer (synthetic lab) export CSV; fx_rates.csv'
ws['D7']=now
ws['B9']='All rows exported through the Expense Viewer export function. NeedsReview/Exceptions are based on MissingReceipt=true from source data.'

rows_sorted=sorted(rows, key=lambda r:(r['ExpenseDate'], r['ExpenseID']))
ws=wb['Details']
for idx,r in enumerate(rows_sorted, start=5):
    cur=r['Currency']
    if cur not in rates:
        raise ValueError(f'Missing FX rate for {cur}')
    amount=Decimal(r['Amount'])
    amount_twd=(amount*rates[cur]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    missing_receipt=str(r.get('MissingReceipt','')).strip().lower() == 'true'
    values=[r['ExpenseID'],r['EmployeeID'],r['EmployeeName'],r['ProjectID'],r['ExpenseDate'],r['Category'],cur,float(amount),float(amount_twd),r['Status'],r.get('ReceiptID',''),r.get('Description',''),str(missing_receipt).lower(),str(missing_receipt).lower()]
    for col,val in enumerate(values, start=1):
        c=ws.cell(idx,col,val)
        if col in [1,2,4,11,13,14]: c.number_format='@'
        elif col==5: c.number_format='yyyy-mm-dd'
        elif col in [8,9]: c.number_format='0.00'

last_formula_row=4+len(rows_sorted) if rows_sorted else 5
ws=wb['Summary']
ws['B2']=f'=SUM(Details!I5:I{last_formula_row})'
summary=defaultdict(lambda:{'amount':Decimal('0'),'twd':Decimal('0'),'count':0})
for r in rows_sorted:
    amount=Decimal(r['Amount'])
    twd=(amount*rates[r['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    key=(r['Status'], r['Currency'])
    summary[key]['amount'] += amount
    summary[key]['twd'] += twd
    summary[key]['count'] += 1
for idx,((status,currency),vals) in enumerate(sorted(summary.items()), start=5):
    row_vals=[status,'',currency,float(vals['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),float(vals['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)),vals['count']]
    for col,val in enumerate(row_vals, start=1):
        c=ws.cell(idx,col,val)
        if col in [4,5]: c.number_format='0.00'
idx=5+len(summary)
ws.cell(idx,1,'TOTAL_TWD')
ws.cell(idx,2,'')
ws.cell(idx,3,'TWD')
ws.cell(idx,4,'')
ws.cell(idx,5,'=B2')
ws.cell(idx,6,len(rows_sorted))
ws.cell(idx,5).number_format='0.00'
for c in ws[idx]: c.font=Font(bold=True)

ws=wb['Exceptions']
exc=[r for r in rows_sorted if str(r.get('MissingReceipt','')).strip().lower()=='true']
for idx,r in enumerate(exc, start=5):
    ws.cell(idx,1,r['ExpenseID']).number_format='@'
    ws.cell(idx,2,r['EmployeeID']).number_format='@'
    ws.cell(idx,3,r['ExpenseDate']).number_format='yyyy-mm-dd'
    ws.cell(idx,4,'MissingReceipt=true')
wb.save(outfile)

# reopen and verify output requirements
check=load_workbook(outfile, data_only=False)
assert check.sheetnames==['Report','Details','Summary','Exceptions','Instructions']
detail=check['Details']
written=[]
r=5
while detail.cell(r,1).value:
    written.append([detail.cell(r,c).value for c in range(1,15)])
    r+=1
assert len(written)==len(rows_sorted)
assert {row[1] for row in written} <= ({employee} if written else {employee})
if written:
    assert min(row[4] for row in written) >= q_from and max(row[4] for row in written) <= q_to
for row in written:
    assert isinstance(row[0], str) and isinstance(row[1], str) and isinstance(row[3], str)
    assert isinstance(row[7], (int,float)) and isinstance(row[8], (int,float))
    assert row[12] in ('true','false') and row[13] in ('true','false')
assert check['Summary']['B2'].value==f'=SUM(Details!I5:I{last_formula_row})'
print('Wrote', outfile)
print('Checked workbook sheets, headers retained, detail row count', len(written), 'employee/date filters, numeric amounts, text IDs, true/false flags, Summary by status/currency with TWD total, Exceptions', len(exc))