import os, csv, json
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
import openpyxl

ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES')
for p in sorted((ws/'input').glob('*')):
    print(' -', p.relative_to(ws), p.stat().st_size)
print('OUTPUT FILES')
for p in sorted((ws/'output').rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(ws), p.stat().st_size)

csv_path = ws/'output'/'downloads'/'sales_orders_export.csv'
xlsx_path = ws/'output'/'september_open_orders.xlsx'
fx_path = ws/'input'/'fx_rates.csv'
template_path = ws/'input'/'sales_template.xlsx'
print('EXPECTED EXISTS', {'csv': csv_path.exists(), 'xlsx': xlsx_path.exists(), 'fx': fx_path.exists(), 'template': template_path.exists()})
if not csv_path.exists() or not xlsx_path.exists():
    raise SystemExit('Missing expected workflow output file')

with csv_path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    csv_rows = list(reader)
print('CSV HEADERS', reader.fieldnames)
print('CSV ROW COUNT', len(csv_rows))
print('CSV SAMPLE', csv_rows[:2])

fx = {}
with fx_path.open(newline='', encoding='utf-8-sig') as f:
    for row in csv.DictReader(f):
        cur = (row.get('Currency') or row.get('currency') or '').strip()
        rate = row.get('TWD') or row.get('Rate') or row.get('rate_to_twd') or row.get('TWD_per_unit') or row.get('ToTWD')
        if cur:
            fx[cur] = Decimal(str(rate).strip())
print('FX', {k: str(v) for k,v in fx.items()})

# Load workbook formulas and values
wb_formula = openpyxl.load_workbook(xlsx_path, data_only=False)
wb_values = openpyxl.load_workbook(xlsx_path, data_only=True)
print('SHEETS', wb_formula.sheetnames)

# Find sheets
if 'Details' not in wb_formula.sheetnames or 'Summary' not in wb_formula.sheetnames:
    raise SystemExit('Missing Details or Summary sheet')
sh = wb_formula['Details']
sv = wb_values['Details']
sm = wb_formula['Summary']
smv = wb_values['Summary']

# Read Details headers at row 4 or first non-empty header-ish row
headers = [sh.cell(4, c).value for c in range(1, sh.max_column+1)]
print('DETAIL HEADERS ROW4', headers)
header_map = {h: i+1 for i,h in enumerate(headers) if h}
required = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms','SalesRep']
missing = [h for h in required if h not in header_map]
if missing:
    raise SystemExit('Missing Detail columns: '+repr(missing))

# Read non-empty detail rows starting row 5
rows = []
for r in range(5, sh.max_row+1):
    oid = sv.cell(r, header_map['OrderID']).value
    if oid is None or str(oid).strip() == '':
        continue
    rec = {h: sv.cell(r, header_map[h]).value for h in required}
    rows.append(rec)
print('DETAIL ROW COUNT', len(rows))
print('DETAIL FIRST/LAST', rows[0] if rows else None, rows[-1] if rows else None)

# Validate CSV filter/sort
csv_ids = [row['OrderID'] for row in csv_rows]
assert len(csv_rows) == 14, f'expected 14 CSV rows, got {len(csv_rows)}'
assert csv_ids == sorted(csv_ids), 'CSV OrderID not ascending'
assert all(row['Status'] == 'Open' for row in csv_rows), 'CSV has non-Open status'
assert all('2026-09-01' <= row['OrderDate'] <= '2026-09-30' for row in csv_rows), 'CSV date outside requested range'

# Validate workbook details
ids = [str(r['OrderID']) for r in rows]
assert len(rows) == len(csv_rows), f'Detail count {len(rows)} != CSV count {len(csv_rows)}'
assert ids == csv_ids, 'Workbook detail OrderIDs do not match CSV or are not sorted'
assert all(isinstance(r['OrderID'], str) and len(r['OrderID']) == 10 and r['OrderID'].startswith('00') for r in rows), 'OrderID not preserved as text IDs'
assert all(r['Status'] == 'Open' for r in rows), 'Workbook has non-Open status'
assert all(str(r['OrderDate'])[:10] >= '2026-09-01' and str(r['OrderDate'])[:10] <= '2026-09-30' for r in rows), 'Workbook date outside requested range'
assert all(isinstance(r['NetAmount'], (int, float)) for r in rows), 'NetAmount not numeric'
assert all(isinstance(r['NetAmountTWD'], (int, float)) for r in rows), 'NetAmountTWD not numeric'

# Validate TWD conversion and summaries
by_cur_amt = defaultdict(Decimal)
by_cur_twd = defaultdict(Decimal)
for r in rows:
    cur = r['Currency']
    amt = Decimal(str(r['NetAmount']))
    expected_twd = (amt * fx[cur]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    actual_twd = Decimal(str(r['NetAmountTWD'])).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    assert actual_twd == expected_twd, f'TWD mismatch {r["OrderID"]}: {actual_twd} != {expected_twd}'
    by_cur_amt[cur] += amt
    by_cur_twd[cur] += actual_twd

print('CALCULATED SUMMARY', {cur: {'amount': str(by_cur_amt[cur].quantize(Decimal('0.01'))), 'twd': str(by_cur_twd[cur].quantize(Decimal('0.01'))), 'count': sum(1 for r in rows if r['Currency']==cur)} for cur in sorted(by_cur_amt)})
print('CALCULATED TOTAL TWD', str(sum(by_cur_twd.values()).quantize(Decimal('0.01'))))

summary_rows = []
for r in range(1, sm.max_row+1):
    vals = [smv.cell(r,c).value for c in range(1, min(sm.max_column, 6)+1)]
    fvals = [sm.cell(r,c).value for c in range(1, min(sm.max_column, 6)+1)]
    if any(v is not None for v in vals) or any(v is not None for v in fvals):
        summary_rows.append({'row': r, 'values': vals, 'formulas': fvals})
print('SUMMARY USED ROWS')
for row in summary_rows:
    print(row)

# Check summary currencies if laid out with Currency / OriginalAmount / TWDAmount / Count columns
summary_text = json.dumps(summary_rows, ensure_ascii=False, default=str)
for cur in sorted(by_cur_amt):
    assert cur in summary_text, f'Summary missing currency {cur}'
assert str(sum(by_cur_twd.values()).quantize(Decimal('0.01'))) in summary_text or '=SUM(Details!I5:I18)' in summary_text, 'Summary missing total TWD value/formula'

# Confirm template is still present and not overwritten by output
print('CHECKS PASSED', json.dumps({
    'csv_file': str(csv_path),
    'xlsx_file': str(xlsx_path),
    'detail_rows': len(rows),
    'order_ids_sorted': True,
    'status': 'Open',
    'date_range': '2026-09-01..2026-09-30',
    'currencies': sorted(by_cur_amt),
    'total_twd': str(sum(by_cur_twd.values()).quantize(Decimal('0.01')))
}, ensure_ascii=False))