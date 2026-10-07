from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
import csv
from openpyxl import load_workbook

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)

# Inputs inspected earlier: template sheets/headers, exported CSV headers/sample rows, FX headers/sample rows.
source_csv = output_dir / 'downloads' / 'sap_sales_orders_2026-09-01_2026-09-30_Open.csv'
template = input_dir / 'sales_template.xlsx'
fx_file = input_dir / 'fx_rates.csv'
outfile = output_dir / 'september_open_orders.xlsx'

print('INPUT source_csv', source_csv, source_csv.exists())
print('INPUT template', template, template.exists())
print('INPUT fx_file', fx_file, fx_file.exists())

# Detail-only fields read through browser detail pages for the downloaded order IDs.
detail_lookup = {
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

# Read FX; note column may contain commas in this test CSV, so only first two fields matter.
fx = {}
with open(fx_file, newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('FX header', header)
    for row in reader:
        if not row or not row[0]:
            continue
        fx[row[0]] = Decimal(row[1])
print('FX rates', fx)

# Read orders from browser export (all filtered rows), sort by text OrderID.
with open(source_csv, newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
print('Export headers', list(rows[0].keys()) if rows else [])
print('Export row_count', len(rows))
rows.sort(key=lambda r: str(r['OrderID']))

# Enrich and convert amounts.
for r in rows:
    oid = str(r['OrderID'])
    r['OrderID'] = oid
    r['CustomerID'] = str(r.get('CustomerID',''))
    r['ProjectID'] = str(r.get('ProjectID','') or '')
    cur = r['Currency']
    amt = Decimal(str(r['NetAmount']))
    if cur not in fx:
        raise ValueError(f'Missing FX rate for {cur}')
    r['NetAmount_dec'] = amt
    r['NetAmountTWD_dec'] = (amt * fx[cur]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    r['CustomerContact'] = detail_lookup.get(oid, {}).get('CustomerContact', '')
    r['PaymentTerms'] = detail_lookup.get(oid, {}).get('PaymentTerms', '')

wb = load_workbook(template)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']

# Report sheet
now = datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
report['B3'] = '2026-09-01'
report['D3'] = '2026-09-30'
report['B4'] = 'Sales Orders; Status=Open; Sort by OrderID asc; all filtered rows exported plus detail pages for contact/payment terms'
report['B5'] = now
report['B7'] = 'Lab ERP synthetic SAP Sales Orders; fx_rates.csv'
report['D7'] = now
report['B9'] = 'ProjectID and CustomerContact left blank where source detail/list is blank. FX uses fixed attachment rates; AmountTWD rounded ROUND_HALF_UP to 2 decimals.'

# Clear existing detail data row 5+
for row in details.iter_rows(min_row=5, max_row=max(details.max_row, 5), max_col=11):
    for c in row:
        c.value = None

# Write details
headers = [details.cell(4, c).value for c in range(1, 12)]
print('Details headers', headers)
for i, r in enumerate(rows, start=5):
    vals = [
        r['OrderID'], r['CustomerID'], r['CustomerName'], r['ProjectID'], r['OrderDate'], r['Status'], r['Currency'],
        float(r['NetAmount_dec']), float(r['NetAmountTWD_dec']), r['CustomerContact'], r['PaymentTerms']
    ]
    for col, val in enumerate(vals, start=1):
        cell = details.cell(i, col, val)
        if col in (1,2,4):
            cell.number_format = '@'
        elif col == 5:
            cell.number_format = 'yyyy-mm-dd'
        elif col in (8,9):
            cell.number_format = '0.00'

# Summary B2 formula and summary rows.
last_row = 4 + len(rows) if rows else 5
summary['B2'] = f'=SUM(Details!I5:I{last_row if rows else 5})'
for row in summary.iter_rows(min_row=5, max_row=max(summary.max_row, 5), max_col=6):
    for c in row:
        c.value = None

by_cur = {}
for r in rows:
    cur = r['Currency']
    item = by_cur.setdefault(cur, {'amount': Decimal('0.00'), 'twd': Decimal('0.00'), 'count': 0})
    item['amount'] += r['NetAmount_dec']
    item['twd'] += r['NetAmountTWD_dec']
    item['count'] += 1

summary_row = 5
for cur in sorted(by_cur):
    item = by_cur[cur]
    values = ['Currency', cur, cur, float(item['amount'].quantize(Decimal('0.01'))), float(item['twd'].quantize(Decimal('0.01'))), item['count']]
    for col, val in enumerate(values, start=1):
        cell = summary.cell(summary_row, col, val)
        if col in (4,5): cell.number_format = '0.00'
    summary_row += 1
# Explicit all-currency TWD total row as requested
total_twd = sum((r['NetAmountTWD_dec'] for r in rows), Decimal('0.00')).quantize(Decimal('0.01'))
values = ['Total', 'All currencies', 'TWD', None, float(total_twd), len(rows)]
for col, val in enumerate(values, start=1):
    cell = summary.cell(summary_row, col, val)
    if col in (4,5): cell.number_format = '0.00'

# Preserve workbook structure, save copy only.
wb.save(outfile)
print('WROTE', outfile)

# Reopen and verify stated requirements.
wb2 = load_workbook(outfile, data_only=False)
assert wb2.sheetnames == ['Report', 'Details', 'Summary', 'Instructions']
rep = wb2['Report']; det = wb2['Details']; summ = wb2['Summary']
assert rep['B3'].value == '2026-09-01' and rep['D3'].value == '2026-09-30'
expected_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
actual_headers = [det.cell(4,c).value for c in range(1,12)]
assert actual_headers == expected_headers, actual_headers
actual_count = 0
ids = []
for row in det.iter_rows(min_row=5, max_row=4+len(rows), max_col=11, values_only=False):
    vals = [c.value for c in row]
    if vals[0] is None: continue
    actual_count += 1
    ids.append(vals[0])
    assert isinstance(vals[0], str) and vals[0].startswith('00')
    assert vals[5] == 'Open'
    assert '2026-09-01' <= vals[4] <= '2026-09-30'
    assert isinstance(vals[7], (int,float)) and isinstance(vals[8], (int,float))
assert actual_count == 14, actual_count
assert ids == sorted(ids), ids
assert summ['B2'].value == '=SUM(Details!I5:I18)'
# Verify summary currency rows and total row
summary_values = [[summ.cell(r,c).value for c in range(1,7)] for r in range(5, 9)]
print('Verified output:', outfile.name)
print('Verified Details rows:', actual_count)
print('Verified sorted OrderIDs:', ids[0], '...', ids[-1])
print('Verified Summary B2:', summ['B2'].value)
print('Summary rows:', summary_values)