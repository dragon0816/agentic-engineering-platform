import csv, json, os, re
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from collections import defaultdict
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

params=json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))
ws=Path.cwd(); inp=ws/'input'; out=ws/'output'; out.mkdir(exist_ok=True)
employee_id=str(params['employee_id'])
date_from=str(params['date_from']); date_to=str(params['date_to'])
output_name=str(params['output_file'])
if not output_name.lower().endswith('.xlsx'):
    raise SystemExit('output_file must end with .xlsx')
export_path=out/f"expense_export_{employee_id}_{date_from}_{date_to}.xlsx"
final_path=out/output_name
if not export_path.exists():
    raise FileNotFoundError(f'Missing desktop export: {export_path}')

def parse_date(v):
    if isinstance(v, datetime): return v.date()
    if isinstance(v, date): return v
    if v is None or str(v).strip()=='': return None
    return datetime.strptime(str(v).strip()[:10], '%Y-%m-%d').date()

def money(v):
    if v is None or str(v).strip()=='': return Decimal('0')
    return Decimal(str(v).replace(',', '').strip())

def round2(v):
    return Decimal(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

def bool_text(v):
    if isinstance(v, bool): return 'true' if v else 'false'
    s='' if v is None else str(v).strip().lower()
    return 'true' if s in {'true','1','yes','y','是'} else 'false'

# Read FX rates. Some notes contain unquoted commas in the lab file; only first two fields matter.
rates={}
with (inp/'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    rdr=csv.reader(f)
    header=next(rdr)
    for row in rdr:
        if len(row)>=2 and row[0]:
            rates[row[0].strip()]=Decimal(row[1].strip())
if not rates:
    raise SystemExit('No FX rates found')

# Read exported workbook first sheet.
ewb=load_workbook(export_path, data_only=True)
esh=ewb[ewb.sheetnames[0]]
rows=list(esh.iter_rows(values_only=True))
if not rows:
    raise SystemExit('Export workbook is empty')
header=[str(c).strip() if c is not None else '' for c in rows[0]]
print('export headers:', header)
records=[]
for row in rows[1:]:
    if not any(v is not None and str(v).strip()!='' for v in row):
        continue
    rec={header[i]: row[i] if i < len(row) else None for i in range(len(header))}
    records.append(rec)
print('export rows:', len(records))

required=['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','Status','ReceiptID','Description','MissingReceipt']
missing=[c for c in required if c not in header]
if missing:
    raise SystemExit(f'Export missing columns: {missing}')

from_d=parse_date(date_from); to_d=parse_date(date_to)
for r in records:
    if str(r.get('EmployeeID','')).strip()!=employee_id:
        raise SystemExit(f"Unexpected EmployeeID {r.get('EmployeeID')} in export")
    d=parse_date(r.get('ExpenseDate'))
    if d is None or d<from_d or d>to_d:
        raise SystemExit(f"ExpenseDate outside requested range: {r.get('ExpenseDate')}")

wb=load_workbook(inp/'expense_template.xlsx')
# Clear old rows below header while preserving sheets.
for s in ['Details','Summary','Exceptions']:
    sh=wb[s]
    if sh.max_row>=5:
        sh.delete_rows(5, sh.max_row-4)

report=wb['Report']
report['B3']=date_from; report['D3']=date_to
report['B4']=f"EmployeeID={employee_id}; Status=all; Source=Expense Viewer export"
report['B5']=datetime.now().isoformat(timespec='seconds')
report['B7']='Expense Viewer'; report['D7']=datetime.now().isoformat(timespec='seconds')
report['B9']=''

details=wb['Details']
summary=wb['Summary']
exceptions=wb['Exceptions']

detail_headers=[details.cell(4,c).value for c in range(1, details.max_column+1)]
expected=['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
if detail_headers[:len(expected)] != expected:
    raise SystemExit(f'Details headers changed: {detail_headers}')

summary_map=defaultdict(lambda: {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
exception_rows=[]
for idx,r in enumerate(records, start=5):
    currency=str(r.get('Currency') or '').strip()
    if currency not in rates:
        raise SystemExit(f'Missing FX rate for {currency}')
    amount=round2(money(r.get('Amount')))
    amount_twd=round2(amount*rates[currency])
    missing_receipt=bool_text(r.get('MissingReceipt'))
    needs_review='true' if missing_receipt=='true' else 'false'
    d=parse_date(r.get('ExpenseDate'))
    values=[
        str(r.get('ExpenseID') or ''),
        str(r.get('EmployeeID') or ''),
        str(r.get('EmployeeName') or ''),
        str(r.get('ProjectID') or ''),
        d,
        str(r.get('Category') or ''),
        currency,
        float(amount),
        float(amount_twd),
        str(r.get('Status') or ''),
        '' if r.get('ReceiptID') is None else str(r.get('ReceiptID')),
        '' if r.get('Description') is None else str(r.get('Description')),
        missing_receipt,
        needs_review,
    ]
    for col,val in enumerate(values, start=1):
        details.cell(idx,col).value=val
    for col in [1,2,4,11,13,14]:
        details.cell(idx,col).number_format='@'
    details.cell(idx,5).number_format='yyyy-mm-dd'
    details.cell(idx,8).number_format='0.00'
    details.cell(idx,9).number_format='0.00'
    key=(str(r.get('Status') or ''), currency)
    summary_map[key]['amount'] += amount
    summary_map[key]['twd'] += amount_twd
    summary_map[key]['count'] += 1
    if missing_receipt=='true':
        exception_rows.append([str(r.get('ExpenseID') or ''), str(r.get('EmployeeID') or ''), d, 'Missing receipt'])

# Summary by status and currency.
for row_idx, ((status,currency), vals) in enumerate(sorted(summary_map.items()), start=5):
    row=[status, currency, currency, float(round2(vals['amount'])), float(round2(vals['twd'])), vals['count']]
    for col,val in enumerate(row, start=1):
        summary.cell(row_idx,col).value=val
    summary.cell(row_idx,4).number_format='0.00'
    summary.cell(row_idx,5).number_format='0.00'

# Summary TWD total formula and note.
last_detail=4+len(records) if records else 5
summary['B2']=f'=SUM(Details!I5:I{last_detail})' if records else '=SUM(Details!I5:I5)'
summary['B2'].number_format='0.00'

for row_idx, row in enumerate(exception_rows, start=5):
    for col,val in enumerate(row, start=1):
        exceptions.cell(row_idx,col).value=val
    exceptions.cell(row_idx,3).number_format='yyyy-mm-dd'

# Basic formatting copied from template row 5 is absent; set practical number/text formats.
for sh in [details, summary, exceptions]:
    sh.freeze_panes='A5'

# Save, then reopen and verify from saved output.
wb.save(final_path)

check=load_workbook(final_path, data_only=False)
for s in ['Report','Details','Summary','Exceptions','Instructions']:
    if s not in check.sheetnames:
        raise SystemExit(f'Missing sheet {s}')
cd=check['Details']; cs=check['Summary']; ce=check['Exceptions']
ch=[cd.cell(4,c).value for c in range(1,15)]
if ch != expected:
    raise SystemExit(f'Output Details headers invalid: {ch}')
actual_rows=[]
for row in cd.iter_rows(min_row=5, max_row=cd.max_row, values_only=True):
    if any(v is not None and str(v)!='' for v in row): actual_rows.append(row)
if len(actual_rows)!=len(records):
    raise SystemExit(f'Details row count {len(actual_rows)} != export {len(records)}')
for row in actual_rows:
    if str(row[1])!=employee_id:
        raise SystemExit('Saved output has unexpected employee')
    d=parse_date(row[4])
    if d<from_d or d>to_d:
        raise SystemExit('Saved output has date outside range')
    if not isinstance(row[7], (int,float)) or not isinstance(row[8], (int,float)):
        raise SystemExit('Saved Amount/AmountTWD not numeric')
    if str(row[12]).lower() not in {'true','false'} or str(row[13]).lower() not in {'true','false'}:
        raise SystemExit('Saved boolean text invalid')
summary_count=0; summary_twd=Decimal('0')
for row in cs.iter_rows(min_row=5, max_row=cs.max_row, values_only=True):
    if any(v is not None and str(v)!='' for v in row):
        summary_count += int(row[5])
        summary_twd += round2(money(row[4]))
detail_twd=sum(round2(money(r[8])) for r in actual_rows)
if summary_count != len(actual_rows):
    raise SystemExit('Summary Count does not match Details rows')
if round2(summary_twd) != round2(detail_twd):
    raise SystemExit('Summary TWD does not match Details TWD')
if cs['B2'].value != (f'=SUM(Details!I5:I{last_detail})' if records else '=SUM(Details!I5:I5)'):
    raise SystemExit('Summary B2 formula range incorrect')
print('created', final_path)
print('kept export', export_path)
print('details rows', len(actual_rows))
print('summary groups', len(summary_map))
print('exceptions rows', len(exception_rows))
print('TWD total', f'{round2(detail_twd):,.2f}')