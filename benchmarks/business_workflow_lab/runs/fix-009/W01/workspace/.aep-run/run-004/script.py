from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from copy import copy
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
import csv, json, re

ws = Path.cwd()
out_dir = ws/'output'
out_dir.mkdir(exist_ok=True)
input_dir = ws/'input'
source_csv = out_dir/'downloads'/'sales_orders_2026-09-01_2026-09-30_Open.csv'
output_xlsx = out_dir/'september_open_orders.xlsx'

print('Inputs really used:')
for p in [input_dir/'sales_template.xlsx', input_dir/'fx_rates.csv', source_csv]:
    print('-', p, 'exists=', p.exists(), 'size=', p.stat().st_size if p.exists() else None)

# Read fx rates; note column may contain commas in this fixture, so only first two columns are used.
fx = {}
with open(input_dir/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    rows = list(csv.reader(f))
    print('fx header/sample:', rows[:4])
    for row in rows[1:]:
        if len(row) >= 2 and row[0].strip():
            fx[row[0].strip()] = Decimal(row[1].strip())
print('fx rates:', fx)

with open(source_csv, newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    records = list(reader)
print('CSV headers:', reader.fieldnames)
print('CSV row count:', len(records))
print('CSV sample rows:', records[:3])

# Detail fields captured from the SAP detail pages through browser operation.
detail_fields = {
 '0045000109': {'CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET10'},
 '0045000110': {'CustomerContact':'張美玲 <mei@tw-precision.example>','PaymentTerms':'NET30'},
 '0045000112': {'CustomerContact':'Peter Ho <peter.ho@acme-limited.example>','PaymentTerms':'NET15'},
 '0045000113': {'CustomerContact':'','PaymentTerms':'NET15'},
 '0045000115': {'CustomerContact':'Sam Patel <sam@pacifictest.example>','PaymentTerms':'NET20'},
 '0045000116': {'CustomerContact':'李建宏 <jh.lee@hsinchu-metrology.example>','PaymentTerms':'NET30'},
 '0045000118': {'CustomerContact':'Jonas Krüger <jk@northwind.example>','PaymentTerms':'NET0'},
 '0045000119': {'CustomerContact':'Grace Lin <grace.lin@acme-precision.example>','PaymentTerms':'NET30'},
 '0045000120': {'CustomerContact':'Eva de Vries <eva@helios.example>','PaymentTerms':'NET10'},
 '0045000122': {'CustomerContact':'張美玲 <mei@tw-precision.example>','PaymentTerms':'NET5'},
 '0045000124': {'CustomerContact':'','PaymentTerms':'NET30'},
 '0045000126': {'CustomerContact':'李建宏 <jh.lee@hsinchu-metrology.example>','PaymentTerms':'NET30'},
 '0045000127': {'CustomerContact':'Peter Ho <peter.ho@acme-limited.example>','PaymentTerms':'NET30'},
 '0045000128': {'CustomerContact':'Jonas Krüger <jk@northwind.example>','PaymentTerms':'NET5'},
}

# Sort and compute TWD
records.sort(key=lambda r: r['OrderID'])
q = Decimal('0.01')
for r in records:
    amt = Decimal(r['NetAmount'])
    cur = r['Currency']
    if cur not in fx:
        raise ValueError(f'Missing FX rate for {cur}')
    r['NetAmountTWD'] = (amt * fx[cur]).quantize(q, rounding=ROUND_HALF_UP)
    r['NetAmountDecimal'] = amt
    r.update(detail_fields.get(r['OrderID'], {'CustomerContact':'','PaymentTerms':''}))

wb = load_workbook(input_dir/'sales_template.xlsx')
report = wb['Report']
details = wb['Details']
summary = wb['Summary']

# Report sheet
now = datetime.now(timezone(timedelta(hours=8))).replace(microsecond=0).isoformat()
report['B3'] = '2026-09-01'
report['D3'] = '2026-09-30'
report['B4'] = 'Sales Orders; Status=Open; Sort by OrderID asc; date field=OrderDate; all filtered rows from Export CSV plus detail pages for contact/payment terms'
report['B5'] = now
report['B7'] = 'Lab ERP synthetic SAP'
report['D7'] = now
report['B9'] = 'All 14 matching September 2026 Open orders were exported; CustomerContact/PaymentTerms were read from order detail pages. Blank ProjectID/CustomerContact cells reflect blank source values.'

# Clear old details below header if any
for row in range(5, max(details.max_row, 5) + 1):
    for col in range(1, 12):
        details.cell(row, col).value = None

# Preserve style from row 5 if present else row 4
style_row = 5 if details.max_row >= 5 else 4
headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
for idx, r in enumerate(records, start=5):
    values = [
        r['OrderID'], r['CustomerID'], r['CustomerName'], r['ProjectID'] or None, r['OrderDate'], r['Status'], r['Currency'],
        float(r['NetAmountDecimal']), float(r['NetAmountTWD']), r.get('CustomerContact') or None, r.get('PaymentTerms') or None
    ]
    for col, val in enumerate(values, start=1):
        cell = details.cell(idx, col)
        cell.value = val
        # copy style from header/data template row where possible
        src = details.cell(4, col)
        cell._style = copy(src._style)
    # text formatting for IDs
    for col in [1,2,4]:
        details.cell(idx,col).number_format = '@'
    details.cell(idx,5).number_format = 'yyyy-mm-dd'
    details.cell(idx,8).number_format = '0.00'
    details.cell(idx,9).number_format = '0.00'

last_row = 4 + len(records) if records else 5
summary['B2'] = f'=SUM(Details!I5:I{last_row if records else 5})'
summary['B2'].number_format = '0.00'

# Summary table: clear row 5+
for row in range(5, max(summary.max_row, 5) + 1):
    for col in range(1, 7):
        summary.cell(row, col).value = None

by_cur = {}
for r in records:
    cur = r['Currency']
    by_cur.setdefault(cur, {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
    by_cur[cur]['amount'] += r['NetAmountDecimal']
    by_cur[cur]['twd'] += r['NetAmountTWD']
    by_cur[cur]['count'] += 1

row = 5
for cur in sorted(by_cur):
    item = by_cur[cur]
    vals = ['Currency', '', cur, float(item['amount'].quantize(q, rounding=ROUND_HALF_UP)), float(item['twd'].quantize(q, rounding=ROUND_HALF_UP)), item['count']]
    for col, val in enumerate(vals, start=1):
        c = summary.cell(row, col)
        c.value = val if val != '' else None
        src = summary.cell(4, col)
        c._style = copy(src._style)
    summary.cell(row,4).number_format='0.00'
    summary.cell(row,5).number_format='0.00'
    row += 1

all_twd = sum((r['NetAmountTWD'] for r in records), Decimal('0'))
vals = ['Total', 'All currencies converted to TWD', 'TWD', None, float(all_twd.quantize(q, rounding=ROUND_HALF_UP)), len(records)]
for col, val in enumerate(vals, start=1):
    c = summary.cell(row, col)
    c.value = val
    src = summary.cell(4, col)
    c._style = copy(src._style)
summary.cell(row,5).number_format='0.00'

# Save
wb.save(output_xlsx)
print('Wrote', output_xlsx)

# Reopen and verify every stated requirement
wb2 = load_workbook(output_xlsx, data_only=False)
assert set(wb2.sheetnames) == set(['Report','Details','Summary','Instructions'])
rd = wb2['Details']
headers_out = [rd.cell(4,c).value for c in range(1,12)]
assert headers_out == headers, headers_out
rows_out = []
for rr in range(5, 5+len(records)):
    rows_out.append([rd.cell(rr,c).value for c in range(1,12)])
assert len(rows_out) == 14, len(rows_out)
ids = [r[0] for r in rows_out]
assert ids == sorted(ids), ids
assert ids[0] == '0045000109' and ids[-1] == '0045000128'
assert all(isinstance(x, str) and len(x)==10 for x in ids)
assert all(r[5] == 'Open' for r in rows_out)
assert all('2026-09-01' <= str(r[4]) <= '2026-09-30' for r in rows_out)
assert all(isinstance(r[7], (int,float)) and isinstance(r[8], (int,float)) for r in rows_out)
# Verify conversion sums
calc_twd = Decimal('0')
for r in rows_out:
    calc_twd += (Decimal(str(r[7])) * fx[r[6]]).quantize(q, rounding=ROUND_HALF_UP)
assert calc_twd == all_twd, (calc_twd, all_twd)
rs = wb2['Summary']
assert rs['B2'].value == '=SUM(Details!I5:I18)', rs['B2'].value
summary_rows = [[rs.cell(rr,c).value for c in range(1,7)] for rr in range(5, 10)]
print('Verification OK:')
print('- output file:', output_xlsx.name)
print('- details rows:', len(rows_out))
print('- order IDs sorted:', ids[0], '...', ids[-1])
print('- currencies:', sorted(by_cur.keys()))
print('- all TWD total:', all_twd)
print('- Summary B2 formula:', rs['B2'].value)
print('- Summary rows:', summary_rows)
