from pathlib import Path
import csv, json
from decimal import Decimal, ROUND_HALF_UP
from openpyxl import load_workbook

ws = Path.cwd()
out = ws/'output'
dl = out/'downloads'
print('workspace:', ws)
print('output files:', sorted(p.name for p in out.iterdir() if p.is_file()))
print('download files:', sorted(p.name for p in dl.iterdir() if p.is_file()) if dl.exists() else [])

csv_path = dl/'sales_orders_raw.csv'
named_csv_path = dl/'september_open_orders_raw.csv'
xlsx_path = out/'september_open_orders.xlsx'
for p in [csv_path, named_csv_path, xlsx_path]:
    print(p, 'exists=', p.exists(), 'size=', p.stat().st_size if p.exists() else None)

with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
    raw_rows = list(csv.DictReader(f))
print('raw csv headers:', list(raw_rows[0].keys()) if raw_rows else [])
print('raw csv row count:', len(raw_rows))
print('raw first 3:', raw_rows[:3])

wb = load_workbook(xlsx_path, data_only=False)
print('workbook sheets:', wb.sheetnames)
for sheet in wb.sheetnames:
    sh = wb[sheet]
    print(sheet, 'max_row=', sh.max_row, 'max_col=', sh.max_column)
    rows = list(sh.iter_rows(values_only=True, max_row=min(sh.max_row, 8)))
    print(sheet, 'sample rows:', rows)

# Locate Details header row and data
assert 'Details' in wb.sheetnames, 'Details sheet missing'
assert 'Summary' in wb.sheetnames, 'Summary sheet missing'
details = wb['Details']
header_row = None
headers = None
for r in range(1, min(details.max_row, 20)+1):
    vals = [details.cell(r,c).value for c in range(1, details.max_column+1)]
    if 'OrderID' in vals and 'NetAmountTWD' in vals:
        header_row = r
        headers = vals
        break
assert header_row, 'Details header row not found'
# trim headers to non-empty last
last = max(i for i,v in enumerate(headers, start=1) if v is not None)
headers = headers[:last]
print('Details header row:', header_row)
print('Details headers:', headers)
required_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','RateToTWD','NetAmountTWD','CustomerContact','PaymentTerms']
assert headers == required_headers, f'Unexpected Details headers: {headers}'
rows=[]
for r in range(header_row+1, details.max_row+1):
    vals = [details.cell(r,c).value for c in range(1, len(headers)+1)]
    if any(v is not None for v in vals):
        rows.append(dict(zip(headers, vals)))
print('Details data row count:', len(rows))
print('Details first 3:', rows[:3])
assert len(rows) == 14, f'Expected 14 detail rows, got {len(rows)}'
assert [str(r['OrderID']) for r in rows] == sorted(str(r['OrderID']) for r in rows), 'OrderID not ascending'
assert all(str(r['Status']) == 'Open' for r in rows), 'Not all statuses Open'
assert all('2026-09-01' <= str(r['OrderDate']) <= '2026-09-30' for r in rows), 'Date outside range'
assert all(str(r['OrderID']).startswith('0045') and len(str(r['OrderID']))==10 for r in rows), 'OrderID text ID format issue'

rates = {'TWD': Decimal('1'), 'USD': Decimal('32'), 'EUR': Decimal('35')}
def q2(x): return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
calc_total = Decimal('0.00')
by_curr = {}
for r in rows:
    cur = str(r['Currency'])
    net = q2(r['NetAmount'])
    rate = Decimal(str(r['RateToTWD']))
    twd = q2(r['NetAmountTWD'])
    expected_twd = q2(net * rates[cur])
    assert rate == rates[cur], f'Rate mismatch {r["OrderID"]}: {rate} != {rates[cur]}'
    assert twd == expected_twd, f'TWD mismatch {r["OrderID"]}: {twd} != {expected_twd}'
    calc_total += twd
    by_curr.setdefault(cur, {'count':0,'net':Decimal('0.00'),'twd':Decimal('0.00')})
    by_curr[cur]['count'] += 1
    by_curr[cur]['net'] += net
    by_curr[cur]['twd'] += twd
calc_total = q2(calc_total)
print('calculated by currency:', {k:{kk:str(vv) for kk,vv in d.items()} for k,d in by_curr.items()})
print('calculated grand total TWD:', calc_total)

# check expected known total
expected_total = Decimal('3431938.70')
assert calc_total == expected_total, f'Grand total expected {expected_total}, got {calc_total}'

# Contact blanks limited to expected known source blanks
blank_contacts = [str(r['OrderID']) for r in rows if r.get('CustomerContact') in (None, '')]
print('blank CustomerContact order IDs:', blank_contacts)
assert blank_contacts == ['0045000113','0045000124'], f'Unexpected blank contacts: {blank_contacts}'

# Validate Summary includes grand total and matches details
summary = wb['Summary']
summary_values = [[summary.cell(r,c).value for c in range(1, summary.max_column+1)] for r in range(1, summary.max_row+1)]
print('Summary values:', summary_values)
flat = [(r, c, v) for r,row in enumerate(summary_values, start=1) for c,v in enumerate(row, start=1)]
gt_cells = [(r,c,v) for r,c,v in flat if isinstance(v, str) and 'Grand Total TWD' in v]
assert gt_cells, 'Grand Total TWD label missing from Summary'
found_total = False
for r,c,v in gt_cells:
    for cc in range(1, summary.max_column+1):
        val = summary.cell(r, cc).value
        if val is not None:
            try:
                if q2(val) == expected_total:
                    found_total = True
            except Exception:
                pass
assert found_total, 'Grand Total TWD value missing or mismatch in Summary'

# named csv should exist and match raw if present
if named_csv_path.exists():
    with named_csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        named_rows = list(csv.DictReader(f))
    print('named raw csv row count:', len(named_rows))
    assert len(named_rows) == 14, 'Named raw CSV row count mismatch'

print('CHECK PASSED: workbook and CSV satisfy stated requirements')
