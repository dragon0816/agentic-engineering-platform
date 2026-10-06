from pathlib import Path
import csv, shutil
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from openpyxl import load_workbook
from copy import copy

workspace = Path.cwd()
input_dir = workspace / 'input'
out_dir = workspace / 'output'
out_dir.mkdir(exist_ok=True)
raw_csv = out_dir / 'downloads' / 'september_open_orders_raw.csv'
template = input_dir / 'sales_template.xlsx'
fx_file = input_dir / 'fx_rates.csv'
out_file = out_dir / 'september_open_orders.xlsx'

print('Inputs:')
print(' raw_csv', raw_csv, raw_csv.exists())
print(' template', template, template.exists())
print(' fx_file', fx_file, fx_file.exists())

# Details retrieved from the SAP-like order detail pages through browser operation.
detail_by_order = {
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

rates = {}
with open(fx_file, newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    print('fx header', header)
    for row in reader:
        if not row or not row[0].strip():
            continue
        rates[row[0].strip()] = Decimal(row[1].strip())
print('rates', rates)

rows = []
with open(raw_csv, newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print('csv columns', reader.fieldnames)
    for r in reader:
        rows.append(r)
rows.sort(key=lambda r: r['OrderID'])
print('raw row count', len(rows))
print('sample rows', rows[:3])

# Validate filter result before creating workbook.
for r in rows:
    if not (date(2026,9,1) <= datetime.strptime(r['OrderDate'], '%Y-%m-%d').date() <= date(2026,9,30)):
        raise ValueError(f"date out of range: {r}")
    if r['Status'] != 'Open':
        raise ValueError(f"non-open row: {r}")
    if r['Currency'] not in rates:
        raise ValueError(f"missing FX rate for {r['Currency']}")
    if r['OrderID'] not in detail_by_order:
        raise ValueError(f"missing detail page values for {r['OrderID']}")

wb = load_workbook(template)
report = wb['Report']
details = wb['Details']
summary = wb['Summary']

# Report metadata
now = datetime.now().replace(microsecond=0).isoformat()
report['B3'] = '2026-09-01'
report['D3'] = '2026-09-30'
report['B4'] = 'Sales Orders; Status=Open; Sort by OrderID asc'
report['B5'] = now
report['B7'] = 'Lab ERP (synthetic SAP-like web)'
report['D7'] = now
report['B9'] = 'Export CSV supplied list fields; CustomerContact and PaymentTerms were read from each order detail page. Blank cells mean source blank.'

# Helper to copy row style/formula from row 5 if needed; template only has header but row 5 style may exist.
def copy_row_style(ws, src_row, dst_row, max_col):
    for col in range(1, max_col+1):
        s = ws.cell(src_row, col)
        d = ws.cell(dst_row, col)
        if s.has_style:
            d._style = copy(s._style)
        if s.number_format:
            d.number_format = s.number_format
        if s.alignment:
            d.alignment = copy(s.alignment)
        if s.font:
            d.font = copy(s.font)
        if s.fill:
            d.fill = copy(s.fill)
        if s.border:
            d.border = copy(s.border)

# Clear existing detail rows from 5 downward (preserve row 4 headers).
if details.max_row >= 5:
    details.delete_rows(5, details.max_row - 4)

q = Decimal('0.01')
summary_by_cur = {}
for idx, r in enumerate(rows, start=5):
    copy_row_style(details, 5, idx, 11)
    net = Decimal(r['NetAmount'])
    twd = (net * rates[r['Currency']]).quantize(q, rounding=ROUND_HALF_UP)
    det = detail_by_order[r['OrderID']]
    values = [
        r['OrderID'], r['CustomerID'], r['CustomerName'], r.get('ProjectID') or None,
        datetime.strptime(r['OrderDate'], '%Y-%m-%d').date(), r['Status'], r['Currency'],
        float(net), float(twd), det.get('CustomerContact') or None, det.get('PaymentTerms') or None,
    ]
    for col, val in enumerate(values, start=1):
        c = details.cell(idx, col, val)
        if col in [1,2,4]:
            c.number_format = '@'
            c.data_type = 's'
        elif col == 5:
            c.number_format = 'yyyy-mm-dd'
        elif col in [8,9]:
            c.number_format = '0.00'
    sb = summary_by_cur.setdefault(r['Currency'], {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0})
    sb['amount'] += net
    sb['twd'] += twd
    sb['count'] += 1

last_detail_row = 4 + len(rows) if rows else 5
summary['B2'] = f'=SUM(Details!I5:I{last_detail_row if rows else 5})'

# Clear old summary data from row 5 downward.
if summary.max_row >= 5:
    summary.delete_rows(5, summary.max_row - 4)

summary_row = 5
for cur in sorted(summary_by_cur):
    sb = summary_by_cur[cur]
    copy_row_style(summary, 5, summary_row, 6)
    vals = ['Currency', cur, cur, float(sb['amount'].quantize(q, rounding=ROUND_HALF_UP)), float(sb['twd'].quantize(q, rounding=ROUND_HALF_UP)), sb['count']]
    for col, val in enumerate(vals, start=1):
        cell = summary.cell(summary_row, col, val)
        if col in [4,5]: cell.number_format = '0.00'
    summary_row += 1
# total TWD row (no original-currency amount to avoid mixing currencies)
total_twd = sum((v['twd'] for v in summary_by_cur.values()), Decimal('0')).quantize(q, rounding=ROUND_HALF_UP)
total_count = sum(v['count'] for v in summary_by_cur.values())
copy_row_style(summary, 5, summary_row, 6)
vals = ['Total', 'All currencies', None, None, float(total_twd), total_count]
for col, val in enumerate(vals, start=1):
    cell = summary.cell(summary_row, col, val)
    if col == 5: cell.number_format = '0.00'

# Autofilter range if present
if len(rows):
    details.auto_filter.ref = f'A4:K{4+len(rows)}'
summary.auto_filter.ref = f'A4:F{summary_row}'

wb.save(out_file)
print('saved', out_file, out_file.stat().st_size)

# Reopen and verify from saved workbook.
wbv = load_workbook(out_file, data_only=False)
dv = wbv['Details']
sv = wbv['Summary']
rv = wbv['Report']
errors = []
expected_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
actual_headers = [dv.cell(4,c).value for c in range(1,12)]
if actual_headers != expected_headers: errors.append(f'headers mismatch {actual_headers}')
if dv.max_row != 18: errors.append(f'Details max_row expected 18 got {dv.max_row}')
ids = [dv.cell(r,1).value for r in range(5, dv.max_row+1)]
if ids != sorted(ids): errors.append('OrderID not sorted')
if len(ids) != 14 or len(set(ids)) != 14: errors.append(f'id count/duplicates wrong {len(ids)} {len(set(ids))}')
for r in range(5, dv.max_row+1):
    oid = dv.cell(r,1).value
    if not isinstance(oid, str) or not oid.startswith('00'): errors.append(f'OrderID not text/leading zeros row {r}: {oid!r}')
    if dv.cell(r,6).value != 'Open': errors.append(f'status not Open row {r}')
    od = dv.cell(r,5).value
    if not isinstance(od, datetime) and not hasattr(od, 'year'):
        errors.append(f'OrderDate not date row {r}: {od!r}')
    if not isinstance(dv.cell(r,8).value, (int,float)): errors.append(f'NetAmount not numeric row {r}')
    if not isinstance(dv.cell(r,9).value, (int,float)): errors.append(f'NetAmountTWD not numeric row {r}')
    # Recompute TWD
    cur = dv.cell(r,7).value
    net = Decimal(str(dv.cell(r,8).value))
    exp = (net * rates[cur]).quantize(q, rounding=ROUND_HALF_UP)
    got = Decimal(str(dv.cell(r,9).value)).quantize(q, rounding=ROUND_HALF_UP)
    if got != exp: errors.append(f'TWD mismatch row {r}: got {got} expected {exp}')
if sv['B2'].value != '=SUM(Details!I5:I18)': errors.append(f'Summary B2 formula {sv["B2"].value}')
summary_rows = [[sv.cell(r,c).value for c in range(1,7)] for r in range(5, sv.max_row+1)]
print('summary rows:', summary_rows)
if not any(row[0]=='Total' and Decimal(str(row[4])).quantize(q)==total_twd for row in summary_rows): errors.append('missing/incorrect total TWD summary row')
if rv['B3'].value != '2026-09-01' or rv['D3'].value != '2026-09-30': errors.append('report dates wrong')
if errors:
    print('CHECK FAILED')
    for e in errors: print('-', e)
    raise SystemExit(1)
print('CHECK PASSED: output workbook reopened; headers, 14 detail rows, sorted text OrderID values, date/status filters, numeric amounts, FX conversions, Summary currency rows and TWD total, and report metadata verified.')