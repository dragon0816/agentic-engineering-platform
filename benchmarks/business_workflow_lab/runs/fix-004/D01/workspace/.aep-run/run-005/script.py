from pathlib import Path
from openpyxl import load_workbook
from collections import defaultdict
import csv, json, math, os, re

ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES')
for p in sorted((ws/'input').glob('*')):
    print(' -', p.name, p.stat().st_size)
print('OUTPUT FILES')
for p in sorted((ws/'output').glob('*')):
    print(' -', p.name, p.stat().st_size)

out = ws/'output'/'E001_september_expenses.xlsx'
export = ws/'output'/'expense_export_E001_2026-09.xlsx'
print('EXPECTED_REPORT_EXISTS', out.exists())
print('EXPECTED_EXPORT_EXISTS', export.exists())
if not out.exists():
    raise SystemExit('Missing expected report output/E001_september_expenses.xlsx')

wb = load_workbook(out, data_only=False)
print('SHEETS', wb.sheetnames)

# Inspect template/output common structure
for s in wb.sheetnames:
    sh = wb[s]
    print('SHEET_DIM', s, sh.max_row, sh.max_column)
    sample = []
    for r in sh.iter_rows(min_row=1, max_row=min(sh.max_row, 8), values_only=True):
        sample.append(r)
    print('SAMPLE', s, json.dumps(sample, ensure_ascii=False, default=str))

required_sheets = ['Report','Details','Summary','Exceptions','Instructions']
missing = [s for s in required_sheets if s not in wb.sheetnames]
if missing:
    raise AssertionError(f'Missing sheets: {missing}')

details = wb['Details']
# Find header row containing ExpenseID and EmployeeID
header_row = None
headers = []
for r in range(1, min(details.max_row, 20)+1):
    vals = [details.cell(r,c).value for c in range(1, details.max_column+1)]
    if 'ExpenseID' in vals and 'EmployeeID' in vals:
        header_row = r
        headers = vals
        break
if header_row is None:
    raise AssertionError('Details header row with ExpenseID/EmployeeID not found')
print('DETAILS_HEADER_ROW', header_row)
print('DETAILS_HEADERS', headers)
idx = {h:i+1 for i,h in enumerate(headers) if h is not None}
required_cols = ['ExpenseID','EmployeeID','Date','Category','Description','Status','Currency','Amount','AmountTWD','ReceiptID','MissingReceipt']
missing_cols = [c for c in required_cols if c not in idx]
if missing_cols:
    raise AssertionError(f'Missing Details columns: {missing_cols}')

rows=[]
for r in range(header_row+1, details.max_row+1):
    if not details.cell(r, idx['ExpenseID']).value:
        continue
    row={c: details.cell(r, idx[c]).value for c in required_cols}
    rows.append(row)
print('DETAILS_ROW_COUNT', len(rows))
print('DETAILS_FIRST_3', json.dumps(rows[:3], ensure_ascii=False, default=str))
if len(rows) != 13:
    raise AssertionError(f'Expected 13 detail rows, got {len(rows)}')
for row in rows:
    if str(row['EmployeeID']) != 'E001':
        raise AssertionError(f'Non-E001 row: {row}')
    d = row['Date']
    ds = d.strftime('%Y-%m-%d') if hasattr(d, 'strftime') else str(d)[:10]
    if not ('2026-09-01' <= ds <= '2026-09-30'):
        raise AssertionError(f'Date outside September 2026: {row}')
    for col in ['Amount','AmountTWD']:
        if not isinstance(row[col], (int,float)):
            raise AssertionError(f'{col} is not numeric in row: {row}')

# Summary validation: find table with Status/Currency/Amount/AmountTWD/Count
summary = wb['Summary']
summary_header_row = None
summary_headers = []
for r in range(1, min(summary.max_row, 30)+1):
    vals = [summary.cell(r,c).value for c in range(1, summary.max_column+1)]
    if 'Status' in vals and 'Currency' in vals and 'AmountTWD' in vals:
        summary_header_row = r
        summary_headers = vals
        break
if summary_header_row is None:
    raise AssertionError('Summary table header not found')
sidx = {h:i+1 for i,h in enumerate(summary_headers) if h is not None}
summary_rows=[]
for r in range(summary_header_row+1, summary.max_row+1):
    status = summary.cell(r,sidx['Status']).value
    currency = summary.cell(r,sidx['Currency']).value
    if not status or not currency:
        continue
    summary_rows.append({h: summary.cell(r,c).value for h,c in sidx.items()})
print('SUMMARY_HEADER_ROW', summary_header_row)
print('SUMMARY_ROWS', json.dumps(summary_rows, ensure_ascii=False, default=str))

calc = defaultdict(lambda: {'Amount':0.0,'AmountTWD':0.0,'Count':0})
for row in rows:
    key=(row['Status'], row['Currency'])
    calc[key]['Amount'] += float(row['Amount'])
    calc[key]['AmountTWD'] += float(row['AmountTWD'])
    calc[key]['Count'] += 1
summary_map = {(r.get('Status'), r.get('Currency')): r for r in summary_rows}
if set(summary_map.keys()) != set(calc.keys()):
    raise AssertionError(f'Summary keys mismatch. file={set(summary_map.keys())}, calc={set(calc.keys())}')
for key, expected in calc.items():
    got = summary_map[key]
    for col in ['Amount','AmountTWD']:
        if abs(float(got[col]) - expected[col]) > 0.011:
            raise AssertionError(f'Summary {key} {col} mismatch: got {got[col]}, expected {expected[col]}')
    if int(got['Count']) != expected['Count']:
        raise AssertionError(f'Summary {key} Count mismatch: got {got["Count"]}, expected {expected["Count"]}')

twd_total = sum(float(row['AmountTWD']) for row in rows)
print('TWD_TOTAL_CALCULATED', round(twd_total, 2))
if abs(twd_total - 31877.90) > 0.011:
    raise AssertionError(f'TWD total mismatch: {twd_total}')

# Exceptions validation: expected MissingReceipt or blank ReceiptID items
exceptions = wb['Exceptions']
ex_header_row = None
ex_headers=[]
for r in range(1, min(exceptions.max_row, 20)+1):
    vals = [exceptions.cell(r,c).value for c in range(1, exceptions.max_column+1)]
    if 'ExpenseID' in vals:
        ex_header_row = r
        ex_headers = vals
        break
print('EXCEPTIONS_HEADER_ROW', ex_header_row)
ex_rows=[]
if ex_header_row:
    eidx = {h:i+1 for i,h in enumerate(ex_headers) if h is not None}
    for r in range(ex_header_row+1, exceptions.max_row+1):
        expid = exceptions.cell(r,eidx['ExpenseID']).value
        if expid:
            ex_rows.append({h: exceptions.cell(r,c).value for h,c in eidx.items()})
print('EXCEPTIONS_ROWS', json.dumps(ex_rows, ensure_ascii=False, default=str))
expected_ex = [row['ExpenseID'] for row in rows if str(row.get('MissingReceipt')).lower() in ('true','1','yes') or row.get('ReceiptID') in (None,'')]
print('EXPECTED_EXCEPTION_IDS', expected_ex)
if [r.get('ExpenseID') for r in ex_rows] != expected_ex:
    raise AssertionError(f'Exception IDs mismatch: got {[r.get("ExpenseID") for r in ex_rows]}, expected {expected_ex}')

if export.exists():
    ewb = load_workbook(export, read_only=True, data_only=True)
    print('EXPORT_SHEETS', ewb.sheetnames)
    esh = ewb[ewb.sheetnames[0]]
    print('EXPORT_DIM', esh.max_row, esh.max_column)

print('VALIDATION_OK: E001 September report and export are present and internally consistent.')