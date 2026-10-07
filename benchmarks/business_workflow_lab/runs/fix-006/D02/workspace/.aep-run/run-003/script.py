from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
import csv, shutil
from collections import defaultdict
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Border, Alignment, Protection

base=Path('.')
in_dir=base/'input'
out_dir=base/'output'
out_dir.mkdir(exist_ok=True)

submitted=out_dir/'submitted_sep2026.csv'
approved=out_dir/'approved_sep2026.csv'
template=in_dir/'expense_template.xlsx'
fx_path=in_dir/'fx_rates.csv'
out_path=out_dir/'expense_report_2026-09_submitted_approved.xlsx'

# Read fx rates: first two columns are authoritative; Note contains commas in this synthetic file.
rates={}
with open(fx_path, newline='', encoding='utf-8-sig') as f:
    rdr=csv.reader(f)
    header=next(rdr)
    for row in rdr:
        if len(row)>=2 and row[0]:
            rates[row[0]]=Decimal(row[1])
print('FX rates:', rates)

# Read exported Expense Viewer rows with detail fields.
rows=[]
for p in [submitted, approved]:
    if not p.exists():
        raise FileNotFoundError(p)
    with open(p, newline='', encoding='utf-8-sig') as f:
        rdr=csv.DictReader(f)
        print(f'{p.name} headers:', rdr.fieldnames)
        for r in rdr:
            rows.append(r)

# Validate requested filter and detail columns.
required_cols=['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','Status','ReceiptID','Description','MissingReceipt']
for r in rows:
    missing=[c for c in required_cols if c not in r]
    if missing:
        raise ValueError(f'Missing columns {missing}')
    if r['Status'] not in {'Submitted','Approved'}:
        raise ValueError(f'Unexpected status {r}')
    if not ('2026-09-01' <= r['ExpenseDate'] <= '2026-09-30'):
        raise ValueError(f'Unexpected date {r}')
    if r['Currency'] not in rates:
        raise ValueError(f'Missing FX rate for {r["Currency"]}')

# Sort by date then ExpenseID for a readable month report.
rows.sort(key=lambda r: (r['ExpenseDate'], r['ExpenseID']))

# Enrich with TWD and normalized booleans.
for r in rows:
    amt=Decimal(r['Amount'])
    twd=(amt * rates[r['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    r['_AmountDec']=amt
    r['_AmountTWDDec']=twd
    r['_Missing']=str(r['MissingReceipt']).strip().lower() == 'true'
    r['_NeedsReview']=r['_Missing']

# Copy template, preserve workbook/sheets/formatting.
shutil.copy2(template, out_path)
wb=load_workbook(out_path)

# Helpers.
def clear_data(ws, start_row, max_col):
    # Delete extra previous data rows, keeping rows above start_row and at least the template row structure.
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)

def copy_row_style(ws, src_row, dst_row, max_col):
    for c in range(1, max_col+1):
        src=ws.cell(src_row, c)
        dst=ws.cell(dst_row, c)
        if src.has_style:
            dst._style = src._style.copy()
        if src.number_format:
            dst.number_format = src.number_format
        if src.alignment:
            dst.alignment = src.alignment.copy()

# Report sheet.
ws=wb['Report']
ws['B3']='2026-09-01'
ws['D3']='2026-09-30'
ws['B4']='ExpenseDate 2026-09-01 through 2026-09-30; Status in Submitted, Approved; all employees/projects'
ws['B5']='2026-10-06T00:00:00+08:00'
ws['B7']='Expense Viewer (synthetic lab); fx_rates.csv'
ws['D7']='2026-10-06T00:00:00+08:00'
missing_count=sum(1 for r in rows if r['_Missing'])
ws['B9']=f'{len(rows)} expenses included; {missing_count} missing receipt expense(s) listed in Exceptions and retained in Details.'

# Details sheet.
ws=wb['Details']
headers=[ws.cell(4,c).value for c in range(1,15)]
print('Details headers:', headers)
clear_data(ws, 5, 14)
# Ensure at least one styled row by copying row 4 style if no row 5 existed after delete.
for idx,r in enumerate(rows, start=5):
    copy_row_style(ws, 4, idx, 14)
    values=[
        r['ExpenseID'], r['EmployeeID'], r['EmployeeName'], r['ProjectID'],
        datetime.strptime(r['ExpenseDate'], '%Y-%m-%d').date(),
        r['Category'], r['Currency'], float(r['_AmountDec']), float(r['_AmountTWDDec']),
        r['Status'], r['ReceiptID'] if r['ReceiptID'] else None, r['Description'] if r['Description'] else None,
        'true' if r['_Missing'] else 'false', 'true' if r['_NeedsReview'] else 'false'
    ]
    for c,val in enumerate(values, start=1):
        cell=ws.cell(idx,c,val)
        if c in [1,2,4,11,13,14]:
            cell.number_format='@'
        elif c==5:
            cell.number_format='yyyy-mm-dd'
        elif c in [8,9]:
            cell.number_format='0.00'
# Set formula range in Summary B2 after details populated.
last_detail_row=4+len(rows) if rows else 5

# Summary sheet by Status and Currency, with Status in Group and blank SubGroup.
ws=wb['Summary']
clear_data(ws, 5, 6)
ws['B2']=f'=SUM(Details!I5:I{last_detail_row if rows else 5})'
summary=defaultdict(lambda: {'amount': Decimal('0'), 'twd': Decimal('0'), 'count':0})
for r in rows:
    key=(r['Status'], '', r['Currency'])
    summary[key]['amount'] += r['_AmountDec']
    summary[key]['twd'] += r['_AmountTWDDec']
    summary[key]['count'] += 1
for idx,(key, agg) in enumerate(sorted(summary.items()), start=5):
    copy_row_style(ws, 4, idx, 6)
    vals=[key[0], key[1] or None, key[2], float(agg['amount'].quantize(Decimal('0.01'))), float(agg['twd'].quantize(Decimal('0.01'))), agg['count']]
    for c,val in enumerate(vals, start=1):
        cell=ws.cell(idx,c,val)
        if c in [4,5]:
            cell.number_format='0.00'
        if c==6:
            cell.number_format='0'

# Exceptions sheet: missing receipts only, retaining Details rows.
ws=wb['Exceptions']
clear_data(ws, 5, 4)
exceptions=[r for r in rows if r['_Missing']]
for idx,r in enumerate(exceptions, start=5):
    copy_row_style(ws, 4, idx, 4)
    vals=[r['ExpenseID'], r['EmployeeID'], datetime.strptime(r['ExpenseDate'], '%Y-%m-%d').date(), 'MissingReceipt=true']
    for c,val in enumerate(vals, start=1):
        cell=ws.cell(idx,c,val)
        if c in [1,2]:
            cell.number_format='@'
        elif c==3:
            cell.number_format='yyyy-mm-dd'

# Preserve filters if present by extending; set practical autofilter ranges on data sheets.
wb['Details'].auto_filter.ref=f'A4:N{last_detail_row if rows else 5}'
last_summary=4+len(summary) if summary else 5
wb['Summary'].auto_filter.ref=f'A4:F{last_summary}'
last_ex=4+len(exceptions) if exceptions else 5
wb['Exceptions'].auto_filter.ref=f'A4:D{last_ex}'

wb.save(out_path)
print('Wrote', out_path)

# Reopen and validate saved output.
wb2=load_workbook(out_path, data_only=False)
# Check sheets unchanged.
expected_sheets=['Report','Details','Summary','Exceptions','Instructions']
assert wb2.sheetnames == expected_sheets, wb2.sheetnames

ws=wb2['Details']
out_headers=[ws.cell(4,c).value for c in range(1,15)]
assert out_headers == ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview'], out_headers
saved_detail_rows=[]
for row in range(5, ws.max_row+1):
    if ws.cell(row,1).value:
        saved_detail_rows.append(row)
assert len(saved_detail_rows)==len(rows), (len(saved_detail_rows), len(rows))
ids=[ws.cell(r,1).value for r in saved_detail_rows]
assert set(ids)==set(r['ExpenseID'] for r in rows)
assert all(ws.cell(r,10).value in ['Submitted','Approved'] for r in saved_detail_rows)
assert all(ws.cell(r,11).value is not None or ws.cell(r,13).value=='true' for r in saved_detail_rows)  # receipt blank only allowed when missing
assert all(isinstance(ws.cell(r,8).value, (int,float)) for r in saved_detail_rows)
assert all(isinstance(ws.cell(r,9).value, (int,float)) for r in saved_detail_rows)

ws=wb2['Exceptions']
ex_ids=[ws.cell(r,1).value for r in range(5, ws.max_row+1) if ws.cell(r,1).value]
expected_ex_ids=[r['ExpenseID'] for r in exceptions]
assert ex_ids==expected_ex_ids, (ex_ids, expected_ex_ids)
# Confirm exception IDs remain in Details.
assert set(ex_ids).issubset(set(ids))

ws=wb2['Summary']
assert ws['B2'].value == f'=SUM(Details!I5:I{last_detail_row})'
summary_rows=[r for r in range(5, ws.max_row+1) if ws.cell(r,1).value]
assert len(summary_rows)==len(summary)

# Compute totals for printed check.
total_twd=sum(r['_AmountTWDDec'] for r in rows)
print('Validated output workbook:')
print(' - Sheets:', wb2.sheetnames)
print(' - Details rows:', len(saved_detail_rows))
print(' - Status counts:', {s: sum(1 for r in rows if r['Status']==s) for s in ['Submitted','Approved']})
print(' - Exception IDs:', ex_ids)
print(' - Summary rows:', len(summary_rows), 'Summary B2:', ws['B2'].value)
print(' - Total AmountTWD:', total_twd)
print('Output file:', out_path.resolve())