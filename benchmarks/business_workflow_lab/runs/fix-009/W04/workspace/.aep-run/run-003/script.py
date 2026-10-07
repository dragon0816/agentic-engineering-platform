from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Alignment
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
import csv, shutil, json

ws = Path.cwd()
input_dir = ws/'input'
out_dir = ws/'output'
out_dir.mkdir(exist_ok=True)

template = input_dir/'sales_template.xlsx'
csv_path = out_dir/'downloads'/'orders_2026-09_open.csv'
output = out_dir/'sales_2026-09_open_filled.xlsx'

print('Inputs:')
for p in [template, input_dir/'fx_rates.csv', csv_path]:
    print(p, 'exists=', p.exists(), 'size=', p.stat().st_size if p.exists() else None)

# Read export CSV, preserving ID text.
with open(csv_path, newline='', encoding='utf-8-sig') as f:
    orders = list(csv.DictReader(f))
print('CSV headers:', orders[0].keys() if orders else [])
print('CSV row count:', len(orders))
print('CSV sample:', orders[:2])

# Details obtained from Lab ERP detail pages via browser operation.
details = {
    '0045000109': {'CustomerContact': 'Grace Lin <grace.lin@acme-precision.example>', 'PaymentTerms': 'NET10'},
    '0045000110': {'CustomerContact': '張美玲 <mei@tw-precision.example>', 'PaymentTerms': 'NET30'},
    '0045000112': {'CustomerContact': 'Peter Ho <peter.ho@acme-limited.example>', 'PaymentTerms': 'NET15'},
    '0045000113': {'CustomerContact': '', 'PaymentTerms': 'NET15'},
    '0045000115': {'CustomerContact': 'Sam Patel <sam@pacifictest.example>', 'PaymentTerms': 'NET20'},
    '0045000116': {'CustomerContact': '李建宏 <jh.lee@hsinchu-metrology.example>', 'PaymentTerms': 'NET30'},
    '0045000118': {'CustomerContact': 'Jonas Krüger <jk@northwind.example>', 'PaymentTerms': 'NET0'},
    '0045000119': {'CustomerContact': 'Grace Lin <grace.lin@acme-precision.example>', 'PaymentTerms': 'NET30'},
    '0045000120': {'CustomerContact': 'Eva de Vries <eva@helios.example>', 'PaymentTerms': 'NET10'},
    '0045000122': {'CustomerContact': '張美玲 <mei@tw-precision.example>', 'PaymentTerms': 'NET5'},
    '0045000124': {'CustomerContact': '', 'PaymentTerms': 'NET30'},
    '0045000126': {'CustomerContact': '李建宏 <jh.lee@hsinchu-metrology.example>', 'PaymentTerms': 'NET30'},
    '0045000127': {'CustomerContact': 'Peter Ho <peter.ho@acme-limited.example>', 'PaymentTerms': 'NET30'},
    '0045000128': {'CustomerContact': 'Jonas Krüger <jk@northwind.example>', 'PaymentTerms': 'NET5'},
}

ids = [r['OrderID'] for r in orders]
missing = sorted(set(ids) - set(details))
extra = sorted(set(details) - set(ids))
print('IDs from CSV:', ids)
print('Detail missing:', missing, 'Detail extra:', extra)
assert not missing and not extra
assert len(ids) == len(set(ids)), 'duplicate OrderID in CSV'

# Read FX rates; notes contain commas in malformed CSV, only first two columns needed.
rates = {}
with open(input_dir/'fx_rates.csv', encoding='utf-8-sig') as f:
    header = f.readline()
    for line in f:
        if not line.strip():
            continue
        parts = line.rstrip('\n').split(',')
        rates[parts[0]] = Decimal(parts[1])
print('FX rates:', rates)

q = Decimal('0.01')
def money(x):
    return Decimal(str(x)).quantize(q, rounding=ROUND_HALF_UP)

def twd(amount, currency):
    return (Decimal(amount) * rates[currency]).quantize(q, rounding=ROUND_HALF_UP)

# Fill a copy of the provided template.
shutil.copyfile(template, output)
wb = load_workbook(output)

# Report sheet.
report = wb['Report']
report['B3'] = '2026-09-01'
report['D3'] = '2026-09-30'
report['B4'] = 'Sales Orders: Status=Open; OrderDate 2026-09-01 to 2026-09-30'
now_iso = datetime.now().astimezone().isoformat(timespec='seconds')
report['B5'] = now_iso
report['B7'] = 'Lab ERP Sales Orders; fx_rates.csv'
report['D7'] = now_iso
report['B9'] = 'Export CSV returned 14 rows. Detail pages fetched for all 14 orders. Session expired once during export and was restored by SSO login; no duplicate or missing OrderID.'

# Details sheet: copy styles/formats from row 5 if present, otherwise row 4.
det = wb['Details']
# Clear existing rows from row 5 down if any.
if det.max_row >= 5:
    det.delete_rows(5, det.max_row - 4)
# Ensure enough rows and fill.
headers = [det.cell(4, c).value for c in range(1, det.max_column+1)]
expected_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
assert headers[:len(expected_headers)] == expected_headers, headers
for idx, r in enumerate(orders, start=5):
    vals = [
        r['OrderID'],
        r['CustomerID'],
        r['CustomerName'],
        r['ProjectID'] or None,
        r['OrderDate'],
        r['Status'],
        r['Currency'],
        float(money(r['NetAmount'])),
        float(twd(r['NetAmount'], r['Currency'])),
        details[r['OrderID']]['CustomerContact'] or None,
        details[r['OrderID']]['PaymentTerms'] or None,
    ]
    for c, v in enumerate(vals, start=1):
        cell = det.cell(idx, c, v)
        if c in [1,2,3,4,6,7,10,11]:
            cell.number_format = '@'
        elif c == 5:
            cell.number_format = 'yyyy-mm-dd'
        elif c in [8,9]:
            cell.number_format = '0.00'
# AutoFilter if exists should cover full data range.
det.auto_filter.ref = f'A4:K{4+len(orders)}'

# Summary sheet.
sumsh = wb['Summary']
# clear old summary rows 5+
if sumsh.max_row >= 5:
    sumsh.delete_rows(5, sumsh.max_row - 4)
last_row = 4 + len(orders)
sumsh['B2'] = f'=SUM(Details!I5:I{last_row})' if orders else '=SUM(Details!I5:I5)'
# Group by Status + Currency (status is fixed Open) to avoid mixing original currencies.
summary = {}
for r in orders:
    key = (r['Status'], '', r['Currency'])
    amount = money(r['NetAmount'])
    amount_twd = twd(r['NetAmount'], r['Currency'])
    if key not in summary:
        summary[key] = {'Amount': Decimal('0'), 'AmountTWD': Decimal('0'), 'Count': 0}
    summary[key]['Amount'] += amount
    summary[key]['AmountTWD'] += amount_twd
    summary[key]['Count'] += 1
for row_idx, (key, agg) in enumerate(sorted(summary.items(), key=lambda kv: kv[0][2]), start=5):
    status, subgroup, currency = key
    vals = [status, None, currency, float(agg['Amount'].quantize(q)), float(agg['AmountTWD'].quantize(q)), agg['Count']]
    for c, v in enumerate(vals, start=1):
        cell = sumsh.cell(row_idx, c, v)
        if c in [1,2,3]: cell.number_format = '@'
        elif c in [4,5]: cell.number_format = '0.00'
        elif c == 6: cell.number_format = '0'
sumsh.auto_filter.ref = f'A4:F{4+len(summary)}'

# Save.
wb.save(output)
print('Wrote:', output)

# Reopen and verify stated requirements.
wb2 = load_workbook(output, data_only=False)
assert wb2.sheetnames == ['Report', 'Details', 'Summary', 'Instructions']
rd = wb2['Report']
assert rd['B3'].value == '2026-09-01' and rd['D3'].value == '2026-09-30'
assert 'Status=Open' in rd['B4'].value

d2 = wb2['Details']
headers2 = [d2.cell(4,c).value for c in range(1,12)]
assert headers2 == expected_headers
rows = []
for rr in range(5, 5+len(orders)):
    rows.append([d2.cell(rr,c).value for c in range(1,12)])
assert len(rows) == 14
out_ids = [str(r[0]) for r in rows]
assert out_ids == ids
assert len(out_ids) == len(set(out_ids))
# ID text / leading zeros preserved
assert all(x.startswith('00') for x in out_ids)
for rr in range(5, 5+len(orders)):
    assert d2.cell(rr,1).number_format == '@'
    assert d2.cell(rr,8).number_format == '0.00'
    assert d2.cell(rr,9).number_format == '0.00'
# source filters: all open and dates in Sep 2026
assert all(d2.cell(rr,6).value == 'Open' for rr in range(5, 5+len(orders)))
assert all('2026-09-01' <= d2.cell(rr,5).value <= '2026-09-30' for rr in range(5, 5+len(orders)))
# Detail fields present; known missing contacts remain blank
contact_by_id = {d2.cell(rr,1).value: d2.cell(rr,10).value for rr in range(5, 5+len(orders))}
assert contact_by_id['0045000113'] is None and contact_by_id['0045000124'] is None
assert d2.cell(5,11).value == 'NET10'
# TWD calculations
for rr, src in zip(range(5, 5+len(orders)), orders):
    expected = float(twd(src['NetAmount'], src['Currency']))
    assert abs(d2.cell(rr,9).value - expected) < 0.001

s2 = wb2['Summary']
assert s2['B2'].value == '=SUM(Details!I5:I18)'
summary_rows = [[s2.cell(rr,c).value for c in range(1,7)] for rr in range(5, 5+len(summary))]
assert len(summary_rows) == 3
assert {r[2] for r in summary_rows} == {'TWD','USD','EUR'}
assert sum(r[5] for r in summary_rows) == 14
print('Verification passed:')
print('- output workbook exists and sheets preserved')
print('- Report period/condition/source filled')
print('- Details headers preserved; 14 rows; OrderID text with leading zero; no duplicates')
print('- all rows are Open and OrderDate within 2026-09-01..2026-09-30')
print('- CustomerContact/PaymentTerms from all detail pages filled; missing contacts blank')
print('- NetAmountTWD uses fx_rates.csv with ROUND_HALF_UP; amount formats set to 0.00')
print('- Summary grouped by Status/Currency with B2 formula =SUM(Details!I5:I18)')
print('Summary rows:', summary_rows)
print('Output file:', output)
