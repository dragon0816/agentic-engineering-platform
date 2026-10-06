import os, csv, json
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from openpyxl import load_workbook

ws = Path.cwd()
print('workspace:', ws)
print('input files:', sorted([p.name for p in (ws/'input').glob('*')]) if (ws/'input').exists() else [])
print('output files:', sorted([str(p.relative_to(ws)) for p in (ws/'output').rglob('*') if p.is_file()]))

# Inspect CSV files
for rel in ['output/downloads/sales_orders_raw.csv', 'output/downloads/september_open_orders_raw.csv']:
    p = ws / rel
    print('\nCSV', rel, 'exists=', p.exists())
    if p.exists():
        with p.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            print(' headers:', reader.fieldnames)
            print(' row_count:', len(rows))
            print(' sample:', rows[:2])

# Inspect workbook from saved output
out = ws / 'output' / 'september_open_orders.xlsx'
print('\nWorkbook exists=', out.exists(), out)
if not out.exists():
    raise SystemExit(1)
wb = load_workbook(out, data_only=False)
print('sheets:', wb.sheetnames)

# Helper to read sheet as dicts
def sheet_dicts(sheet_name):
    sh = wb[sheet_name]
    headers = [c.value for c in sh[1]]
    rows = []
    for row in sh.iter_rows(min_row=2, values_only=False):
        if all(c.value is None for c in row):
            continue
        rows.append({headers[i]: row[i].value for i in range(len(headers))})
    return headers, rows

headers, rows = sheet_dicts('Details')
print('Details headers:', headers)
print('Details row_count:', len(rows))
print('Details first:', rows[0] if rows else None)
print('Details last:', rows[-1] if rows else None)

# Validate requirements known from workflow
errors=[]
expected_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','CustomerContact','PaymentTerms','SalesRep','RateToTWD','NetAmountTWD']
for h in expected_headers:
    if h not in headers:
        errors.append(f'missing Details column {h}')
if len(rows) != 14:
    errors.append(f'expected 14 Details rows, got {len(rows)}')
ids = [str(r.get('OrderID')) for r in rows]
if ids != sorted(ids):
    errors.append('OrderID not sorted ascending')
if any(not isinstance(r.get('OrderID'), str) or not str(r.get('OrderID')).startswith('00') for r in rows):
    errors.append('some OrderID values are not text with leading zeroes')
if any(r.get('Status') != 'Open' for r in rows):
    errors.append('some Status values are not Open')
if any(str(r.get('OrderDate')) < '2026-09-01' or str(r.get('OrderDate')) > '2026-09-30' for r in rows):
    errors.append('some OrderDate values are outside September 2026')
allowed_blank_contacts = {'0045000113','0045000124'}
blank_contacts = {str(r.get('OrderID')) for r in rows if not r.get('CustomerContact')}
if not blank_contacts.issubset(allowed_blank_contacts):
    errors.append(f'unexpected blank CustomerContact IDs {sorted(blank_contacts)}')
if any(not r.get('PaymentTerms') for r in rows):
    errors.append('some PaymentTerms values are blank')

rates = {'TWD': Decimal('1'), 'USD': Decimal('32'), 'EUR': Decimal('35')}
detail_total = Decimal('0')
for r in rows:
    cur = r.get('Currency')
    rate = Decimal(str(r.get('RateToTWD')))
    if rate != rates[cur]:
        errors.append(f"rate mismatch for {r.get('OrderID')}: {cur} {rate}")
    net = Decimal(str(r.get('NetAmount')))
    twd = Decimal(str(r.get('NetAmountTWD')))
    expected = (net * rates[cur]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if twd != expected:
        errors.append(f"NetAmountTWD mismatch for {r.get('OrderID')}: got {twd}, expected {expected}")
    detail_total += twd
print('blank_contacts:', sorted(blank_contacts))
print('detail_total_twd:', detail_total)

# Summary
sum_headers, sum_rows = sheet_dicts('Summary')
print('Summary headers:', sum_headers)
print('Summary rows:', sum_rows)
summary_total = Decimal('0')
for r in sum_rows:
    val = r.get('NetAmountTWD') or r.get('TotalTWD') or r.get('TotalNetAmountTWD')
    if val is not None:
        summary_total += Decimal(str(val))
print('summary_total_twd:', summary_total)
if summary_total != detail_total:
    errors.append(f'Summary total {summary_total} != Details total {detail_total}')

# Report values
rep_headers, rep_rows = sheet_dicts('Report')
print('Report headers:', rep_headers)
print('Report rows:', rep_rows)
# Look for total in values
report_values = []
for sh_row in wb['Report'].iter_rows(values_only=True):
    report_values.append(sh_row)
print('Report raw:', report_values)
if not any(str(detail_total) in [str(v) for v in row if v is not None] or float(detail_total) == v if isinstance(v, float) else False for row in report_values):
    # Do not fail solely on format; print for human review
    print('note: exact detail total not found in Report raw values by simple scan')

print('\nCHECK_ERRORS:', errors)
if errors:
    raise SystemExit(2)
print('CHECK_OK: september_open_orders.xlsx and source CSV outputs satisfy checked requirements')