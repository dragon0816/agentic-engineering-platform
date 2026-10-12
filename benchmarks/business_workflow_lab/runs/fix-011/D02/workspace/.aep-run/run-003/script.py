from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from openpyxl.utils import get_column_letter
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
import csv, datetime, shutil, os, re

ws = Path.cwd()
input_dir = ws/'input'
output_dir = ws/'output'
output_dir.mkdir(exist_ok=True)
submitted_csv = output_dir/'submitted_2026_09.csv'
approved_csv = output_dir/'approved_2026_09.csv'

print('Inputs used:')
for p in [input_dir/'expense_template.xlsx', input_dir/'fx_rates.csv', submitted_csv, approved_csv]:
    print(' ', p, 'exists=', p.exists(), 'size=', p.stat().st_size if p.exists() else None)

# read fx rates (CSV note has commas, only first 2 columns matter)
fx = {}
with open(input_dir/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if not row or not row[0].strip():
            continue
        fx[row[0].strip()] = Decimal(row[1].strip())
print('FX rates:', fx)

# read exported rows
def read_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        print(path.name, 'headers:', reader.fieldnames, 'rows:', len(rows))
        for r in rows[:3]: print(' sample', r)
        return rows
rows = read_rows(submitted_csv) + read_rows(approved_csv)

# restrict and validate criteria
wanted_status = {'Submitted', 'Approved'}
from_date = datetime.date(2026,9,1)
to_date = datetime.date(2026,9,30)
filtered = []
for r in rows:
    d = datetime.date.fromisoformat(r['ExpenseDate'])
    if from_date <= d <= to_date and r['Status'] in wanted_status:
        filtered.append(r)
    else:
        raise ValueError(f'Out of requested criteria in export: {r}')
# de-dupe by ExpenseID preserving info, no expected duplicates
seen = set()
dedup = []
for r in filtered:
    eid = r['ExpenseID']
    if eid in seen:
        raise ValueError('duplicate ExpenseID ' + eid)
    seen.add(eid)
    dedup.append(r)
rows = sorted(dedup, key=lambda r: (r['ExpenseDate'], r['ExpenseID']))
print('Combined requested rows:', len(rows))
print('MissingReceipt rows:', [r['ExpenseID'] for r in rows if r.get('MissingReceipt','').strip().lower() == 'true'])

# load template and preserve workbook
src = input_dir/'expense_template.xlsx'
out = output_dir/'expense_report_2026_09_submitted_approved.xlsx'
shutil.copyfile(src, out)
wb = load_workbook(out)

# helpers
DETAIL_HEADERS = ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview']
SUMMARY_HEADERS = ['Group','SubGroup','Currency','Amount','AmountTWD','Count']
EXC_HEADERS = ['ExpenseID','EmployeeID','ExpenseDate','Reason']

def clear_data(sheet, start_row, max_col):
    # delete data rows beyond header, keeping formatting/layout above
    if sheet.max_row >= start_row:
        sheet.delete_rows(start_row, sheet.max_row - start_row + 1)
    # ensure at least header row remains; no blank data row needed

def copy_row_style(sheet, source_row, target_row, max_col):
    for col in range(1, max_col+1):
        src_cell = sheet.cell(source_row, col)
        dst_cell = sheet.cell(target_row, col)
        if src_cell.has_style:
            dst_cell._style = copy(src_cell._style)
        if src_cell.number_format:
            dst_cell.number_format = src_cell.number_format
        if src_cell.alignment:
            dst_cell.alignment = copy(src_cell.alignment)
        if src_cell.font:
            dst_cell.font = copy(src_cell.font)
        if src_cell.fill:
            dst_cell.fill = copy(src_cell.fill)
        if src_cell.border:
            dst_cell.border = copy(src_cell.border)
        if src_cell.protection:
            dst_cell.protection = copy(src_cell.protection)

def amount_twd(amount, currency):
    a = Decimal(str(amount))
    rate = fx[currency]
    return (a * rate).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# Report sheet
report = wb['Report']
now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).replace(microsecond=0).isoformat()
report['B3'] = '2026-09-01'
report['D3'] = '2026-09-30'
report['B4'] = 'ExpenseDate 2026-09-01 to 2026-09-30; Status in Submitted, Approved'
report['B5'] = now
report['B7'] = 'Expense Viewer (synthetic lab) export CSV'
report['D7'] = now
missing_ids = [r['ExpenseID'] for r in rows if r.get('MissingReceipt','').strip().lower() == 'true']
report['B9'] = f'{len(rows)} expenses included. Missing receipts retained in Details and listed in Exceptions: ' + (', '.join(missing_ids) if missing_ids else 'none')

# Details
sh = wb['Details']
headers = [sh.cell(4,c).value for c in range(1, len(DETAIL_HEADERS)+1)]
if headers != DETAIL_HEADERS:
    raise ValueError(f'Details headers differ: {headers}')
clear_data(sh, 5, len(DETAIL_HEADERS))
for i, r in enumerate(rows, start=5):
    if i > 5:
        copy_row_style(sh, 5, i, len(DETAIL_HEADERS))
    amt = Decimal(r['Amount'])
    twd = amount_twd(amt, r['Currency'])
    missing = r.get('MissingReceipt','').strip().lower() == 'true'
    values = [
        r['ExpenseID'], r['EmployeeID'], r['EmployeeName'], r['ProjectID'],
        datetime.date.fromisoformat(r['ExpenseDate']), r['Category'], r['Currency'],
        float(amt), float(twd), r['Status'], r.get('ReceiptID') or None,
        r.get('Description') or None, str(missing).lower(), str(missing).lower()
    ]
    for c, v in enumerate(values, start=1):
        cell = sh.cell(i, c, v)
        if c in [1,2,3,4,6,7,10,11,12,13,14]:
            cell.number_format = '@'
        elif c == 5:
            cell.number_format = 'yyyy-mm-dd'
        elif c in [8,9]:
            cell.number_format = '0.00'
    sh.cell(i, 12).alignment = Alignment(wrap_text=True, vertical='top')
# Auto-filter if existing? set to header/data range
sh.auto_filter.ref = f'A4:N{4+len(rows)}'

# Summary: group by Status then Currency (matches requested statuses and avoids mixing currencies)
sumsh = wb['Summary']
headers = [sumsh.cell(4,c).value for c in range(1, len(SUMMARY_HEADERS)+1)]
if headers != SUMMARY_HEADERS:
    raise ValueError(f'Summary headers differ: {headers}')
clear_data(sumsh, 5, len(SUMMARY_HEADERS))
summary = {}
for r in rows:
    key = (r['Status'], r['Currency'])
    amt = Decimal(r['Amount'])
    twd = amount_twd(amt, r['Currency'])
    if key not in summary:
        summary[key] = {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0}
    summary[key]['amount'] += amt
    summary[key]['twd'] += twd
    summary[key]['count'] += 1
for i, ((status, currency), vals) in enumerate(sorted(summary.items()), start=5):
    if i > 5:
        copy_row_style(sumsh, 5, i, len(SUMMARY_HEADERS))
    vals_list = [status, '', currency, float(vals['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), float(vals['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), vals['count']]
    for c, v in enumerate(vals_list, start=1):
        cell = sumsh.cell(i, c, v)
        if c in [1,2,3]: cell.number_format='@'
        elif c in [4,5]: cell.number_format='0.00'
        elif c==6: cell.number_format='0'
last_detail = 4 + len(rows) if rows else 5
sumsh['B2'] = f'=SUM(Details!I5:I{last_detail if rows else 5})'
sumsh.auto_filter.ref = f'A4:F{4+len(summary)}'

# Exceptions: missing receipts only; original ExpenseID retained
ex = wb['Exceptions']
headers = [ex.cell(4,c).value for c in range(1, len(EXC_HEADERS)+1)]
if headers != EXC_HEADERS:
    raise ValueError(f'Exceptions headers differ: {headers}')
clear_data(ex, 5, len(EXC_HEADERS))
exc_rows = [r for r in rows if r.get('MissingReceipt','').strip().lower() == 'true']
for i, r in enumerate(exc_rows, start=5):
    if i > 5:
        copy_row_style(ex, 5, i, len(EXC_HEADERS))
    vals=[r['ExpenseID'], r['EmployeeID'], datetime.date.fromisoformat(r['ExpenseDate']), 'Missing receipt']
    for c, v in enumerate(vals, start=1):
        cell=ex.cell(i,c,v)
        if c in [1,2,4]: cell.number_format='@'
        elif c==3: cell.number_format='yyyy-mm-dd'
ex.auto_filter.ref = f'A4:D{4+len(exc_rows)}'

# Save
wb.save(out)
print('Wrote', out)

# Reopen validation: values, counts, formulas, no deletion of missing rows
wb2 = load_workbook(out, data_only=False)
d = wb2['Details']; s=wb2['Summary']; e=wb2['Exceptions']; rsh=wb2['Report']
# read details back
detail_rows=[]
for row in d.iter_rows(min_row=5, max_row=4+len(rows), max_col=14, values_only=True):
    detail_rows.append(row)
print('\nVALIDATION')
print('Report B3/D3/B4:', rsh['B3'].value, rsh['D3'].value, rsh['B4'].value)
print('Details rows:', len(detail_rows))
print('Details headers:', [d.cell(4,c).value for c in range(1,15)])
print('Summary formula B2:', s['B2'].value)
print('Summary rows:', len(summary), sorted(summary.items()))
print('Exceptions rows:', len(exc_rows), [e.cell(i,1).value for i in range(5,5+len(exc_rows))])
# assertions
assert len(detail_rows) == 22, len(detail_rows)
assert set(x[9] for x in detail_rows) == {'Submitted','Approved'}
assert all(from_date <= (x[4] if isinstance(x[4], datetime.date) else datetime.date.fromisoformat(x[4])) <= to_date for x in detail_rows)
# exact columns/text/numbers
for x in detail_rows:
    eid, empid, _, _, dt, cat, curr, amt, twd, status, receipt, desc, missing, needs = x
    assert isinstance(eid, str) and eid.startswith('EXP-')
    assert isinstance(empid, str)
    assert isinstance(amt, (int,float))
    assert isinstance(twd, (int,float))
    assert missing in ('true','false') and needs in ('true','false')
    if missing == 'true':
        assert needs == 'true'
    assert desc is None or isinstance(desc, str)
# Missing expense IDs still in Details and in Exceptions
missing_in_details = [x[0] for x in detail_rows if x[12] == 'true']
exception_ids = [e.cell(i,1).value for i in range(5, 5+len(exc_rows))]
assert missing_in_details == missing_ids
assert exception_ids == missing_ids
# Recompute TWD and compare by ExpenseID
by_id = {r['ExpenseID']: r for r in rows}
for x in detail_rows:
    rr=by_id[x[0]]
    expected=float(amount_twd(Decimal(rr['Amount']), rr['Currency']))
    assert abs(x[8]-expected) < 0.0001, (x[0], x[8], expected)
# Check summary totals vs details
assert s['B2'].value == '=SUM(Details!I5:I26)'
print('All checks passed. Output file:', out.name)
print('Output absolute path:', out)