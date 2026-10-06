import csv, io, os, re, urllib.request, urllib.parse, http.cookiejar, html
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from copy import copy
from openpyxl import load_workbook

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
OUT_XLSX = OUTPUT / 'sales_template_filled.xlsx'
OUT_SUMMARY = OUTPUT / 'sales_order_summary.txt'

CUSTOMER_ID = 'C001'
DATE_FROM = '2026-08-01'
DATE_TO = '2026-10-31'
BASE_URL = 'http://127.0.0.1:8810'

# Read FX rates. The Note column contains commas in this lab file; only first two columns are required.
fx_rates = {}
with open(INPUT / 'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2 and row[0].strip():
            fx_rates[row[0].strip()] = Decimal(row[1].strip())
print('FX rates loaded:', fx_rates)

# Browser-less SSO session for the local ERP.
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def request(path, data=None):
    if data is not None:
        data = urllib.parse.urlencode(data).encode('utf-8')
    resp = opener.open(BASE_URL + path, data=data, timeout=20)
    raw = resp.read()
    content_type = resp.headers.get('Content-Type', '')
    encoding = 'utf-8-sig' if 'csv' in content_type or path.endswith('.csv') else 'utf-8'
    return resp.geturl(), raw.decode(encoding, errors='replace')

# Sign in if needed.
url, body = request('/')
if '/login' in url or '<h1>Sign in</h1>' in body:
    request('/login', {'next': '/orders', 'sso': 'company'})

query = urllib.parse.urlencode({'customer': CUSTOMER_ID, 'from': DATE_FROM, 'to': DATE_TO})
list_url, list_body = request('/orders?' + query)
print('Filtered orders page:', list_url)
count_match = re.search(r"Total:\s*<strong>(\d+)</strong>\s*rows", list_body)
page_count = int(count_match.group(1)) if count_match else None
print('ERP filtered row count shown:', page_count)

# Export exactly filtered rows. Use customer= (per manual form name), not name search; later verify every CustomerID is C001.
export_url, csv_text = request('/orders/export.csv?' + query)
orders = list(csv.DictReader(io.StringIO(csv_text)))
print('Export URL:', export_url)
print('Export row count:', len(orders))
print('Export CustomerIDs:', sorted({r.get('CustomerID', '') for r in orders}))
print('Export OrderIDs:', [r.get('OrderID') for r in orders])

# Helper to parse detail header table: data-field attributes are enough for required fields.
def parse_data_fields(doc):
    fields = {}
    # Capture td content with a data-field. If an anchor is inside, strip tags and unescape text.
    for m in re.finditer(r"<td\s+data-field=['\"]([^'\"]+)['\"](?:\s+class=['\"][^'\"]*['\"])?>(.*?)</td>", doc, flags=re.I | re.S):
        key = m.group(1)
        val = re.sub(r'<[^>]+>', '', m.group(2))
        fields[key] = html.unescape(val).strip()
    return fields

# Enter each order detail to get CustomerContact and PaymentTerms; also cross-check header.
detailed = []
missing_by_order = {}
for row in orders:
    oid = row['OrderID']
    detail_url, detail_html = request('/orders/' + urllib.parse.quote(oid))
    fields = parse_data_fields(detail_html)
    merged = dict(row)
    for k in ['CustomerContact', 'PaymentTerms']:
        merged[k] = fields.get(k, '')
    # Cross-check key header fields where present; keep export values if there is no conflict.
    conflicts = []
    for k in ['OrderID', 'CustomerID', 'CustomerName', 'ProjectID', 'OrderDate', 'Status', 'Currency', 'NetAmount']:
        if k in fields and str(fields[k]) != str(row.get(k, '')):
            conflicts.append(f'{k}: export={row.get(k)!r}, detail={fields[k]!r}')
    if conflicts:
        raise RuntimeError(f'Detail conflict for {oid}: ' + '; '.join(conflicts))
    if merged.get('CustomerID') != CUSTOMER_ID:
        raise RuntimeError(f'Non-target customer mixed in: order {oid} CustomerID={merged.get("CustomerID")}')
    missing = [k for k in ['ProjectID', 'CustomerContact', 'PaymentTerms'] if not merged.get(k)]
    if missing:
        missing_by_order[oid] = missing
    detailed.append(merged)
    print('Detail fetched:', oid, 'CustomerContact=', merged['CustomerContact'] or '<blank>', 'PaymentTerms=', merged['PaymentTerms'] or '<blank>')

# Sort stable by OrderDate then OrderID.
detailed.sort(key=lambda r: (r['OrderDate'], r['OrderID']))

# Prepare workbook.
wb = load_workbook(INPUT / 'sales_template.xlsx')
ws_report = wb['Report']
ws_details = wb['Details']
ws_summary = wb['Summary']

# Clear possible pre-existing data rows while preserving headers and template structure.
for ws, min_row in [(ws_details, 5), (ws_summary, 5)]:
    if ws.max_row >= min_row:
        ws.delete_rows(min_row, ws.max_row - min_row + 1)

now_iso = datetime.now().astimezone().isoformat(timespec='seconds')
ws_report['B3'] = DATE_FROM
ws_report['D3'] = DATE_TO
ws_report['B4'] = f'CustomerID exact match {CUSTOMER_ID}; Sales Orders OrderDate {DATE_FROM} to {DATE_TO} inclusive'
ws_report['B5'] = now_iso
ws_report['B7'] = 'Lab ERP Sales Orders; fx_rates.csv'
ws_report['D7'] = now_iso

# Missing notes.
if missing_by_order:
    missing_notes = '; '.join(f"{oid}: {', '.join(cols)}" for oid, cols in missing_by_order.items())
else:
    missing_notes = '未缺資料；所有訂單皆有 CustomerContact 與 PaymentTerms。'
ws_report['B9'] = missing_notes

# Copy styles from first data row if present/blank template row, otherwise header-based minimal formatting.
headers = [ws_details.cell(4, c).value for c in range(1, 12)]
assert headers == ['OrderID', 'CustomerID', 'CustomerName', 'ProjectID', 'OrderDate', 'Status', 'Currency', 'NetAmount', 'NetAmountTWD', 'CustomerContact', 'PaymentTerms']

# Fill details.
for idx, r in enumerate(detailed, start=5):
    amount = Decimal(r['NetAmount'])
    currency = r['Currency']
    if currency not in fx_rates:
        raise RuntimeError(f'Missing FX rate for {currency}')
    amount_twd = (amount * fx_rates[currency]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    values = [
        str(r['OrderID']), str(r['CustomerID']), r['CustomerName'], str(r.get('ProjectID') or ''), r['OrderDate'],
        r['Status'], currency, float(amount), float(amount_twd), r.get('CustomerContact') or '', r.get('PaymentTerms') or ''
    ]
    for c, value in enumerate(values, start=1):
        cell = ws_details.cell(idx, c, value)
        # Preserve ID columns as text.
        if c in [1, 2, 4, 5, 6, 7, 10, 11]:
            cell.number_format = '@' if c in [1, 2, 4] else 'yyyy-mm-dd' if c == 5 else 'General'
        if c in [8, 9]:
            cell.number_format = '0.00'

# Summary grouped by Status and Currency to avoid mixing original currencies.
summary = {}
for r in detailed:
    key = (r['Status'], r['Currency'])
    amount = Decimal(r['NetAmount'])
    amount_twd = (amount * fx_rates[r['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if key not in summary:
        summary[key] = {'amount': Decimal('0.00'), 'amount_twd': Decimal('0.00'), 'count': 0}
    summary[key]['amount'] += amount
    summary[key]['amount_twd'] += amount_twd
    summary[key]['count'] += 1

rownum = 5
for (status, currency), agg in sorted(summary.items(), key=lambda kv: (kv[0][0], kv[0][1])):
    ws_summary.cell(rownum, 1, 'Status')
    ws_summary.cell(rownum, 2, status)
    ws_summary.cell(rownum, 3, currency)
    ws_summary.cell(rownum, 4, float(agg['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)))
    ws_summary.cell(rownum, 5, float(agg['amount_twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)))
    ws_summary.cell(rownum, 6, agg['count'])
    ws_summary.cell(rownum, 4).number_format = '0.00'
    ws_summary.cell(rownum, 5).number_format = '0.00'
    rownum += 1

last_detail_row = 4 + len(detailed) if detailed else 5
if detailed:
    ws_summary['B2'] = f'=SUM(Details!I5:I{last_detail_row})'
else:
    ws_summary['B2'] = '=SUM(Details!I5:I5)'

# Save workbook.
wb.save(OUT_XLSX)

# Create an external summary text too.
summary_lines = [
    f'CustomerID: {CUSTOMER_ID} (exact match only)',
    f'Date range: {DATE_FROM} to {DATE_TO} inclusive',
    f'Orders included: {len(detailed)}',
    'OrderIDs: ' + ', '.join(r['OrderID'] for r in detailed),
    'Similar-name customer exclusion: verified every exported/detail row has CustomerID C001.',
    'Missing data: ' + missing_notes,
]
OUT_SUMMARY.write_text('\n'.join(summary_lines) + '\n', encoding='utf-8')

# Verification: reopen outputs and confirm requirements from saved files.
wb2 = load_workbook(OUT_XLSX, data_only=False)
wd = wb2['Details']
ws = wb2['Summary']
wr = wb2['Report']
actual_headers = [wd.cell(4, c).value for c in range(1, 12)]
errors = []
if actual_headers != headers:
    errors.append(f'Headers changed: {actual_headers}')
if wr['B3'].value != DATE_FROM or wr['D3'].value != DATE_TO:
    errors.append('Report date range cells not set correctly')
if wd.max_row != 4 + len(detailed):
    errors.append(f'Details row count mismatch: max_row={wd.max_row}, expected={4+len(detailed)}')
# Verify all detail rows.
seen_oids = []
calc_total_twd = Decimal('0.00')
for r in range(5, wd.max_row + 1):
    oid = wd.cell(r, 1).value
    seen_oids.append(oid)
    if not isinstance(oid, str) or not oid.startswith('00'):
        errors.append(f'OrderID not preserved as text with leading zeros at row {r}: {oid!r}')
    if wd.cell(r, 2).value != CUSTOMER_ID:
        errors.append(f'Non-C001 CustomerID at row {r}: {wd.cell(r,2).value!r}')
    order_date = wd.cell(r, 5).value
    if not (DATE_FROM <= str(order_date) <= DATE_TO):
        errors.append(f'OrderDate outside range at row {r}: {order_date!r}')
    for c in [8, 9]:
        if not isinstance(wd.cell(r, c).value, (int, float)):
            errors.append(f'Amount column {c} is not numeric at row {r}: {wd.cell(r,c).value!r}')
    if wd.cell(r, 10).value is None:
        errors.append(f'CustomerContact is missing/None at row {r}')
    if wd.cell(r, 11).value is None:
        errors.append(f'PaymentTerms is missing/None at row {r}')
    calc_total_twd += Decimal(str(wd.cell(r, 9).value)).quantize(Decimal('0.01'))
if seen_oids != [r['OrderID'] for r in detailed]:
    errors.append(f'OrderID order mismatch: {seen_oids}')
if set(seen_oids) != set(r['OrderID'] for r in detailed):
    errors.append('OrderID set mismatch')
if ws['B2'].value != f'=SUM(Details!I5:I{last_detail_row})':
    errors.append(f'Summary B2 formula mismatch: {ws["B2"].value!r}')
# Verify summary row counts and totals.
summary_count = 0
summary_twd = Decimal('0.00')
for r in range(5, ws.max_row + 1):
    if ws.cell(r,1).value is None:
        continue
    if ws.cell(r,1).value != 'Status':
        errors.append(f'Unexpected Summary Group at row {r}: {ws.cell(r,1).value!r}')
    if not isinstance(ws.cell(r,4).value, (int,float)) or not isinstance(ws.cell(r,5).value, (int,float)):
        errors.append(f'Summary numeric values invalid at row {r}')
    summary_count += int(ws.cell(r,6).value)
    summary_twd += Decimal(str(ws.cell(r,5).value)).quantize(Decimal('0.01'))
if summary_count != len(detailed):
    errors.append(f'Summary count mismatch: {summary_count} vs {len(detailed)}')
if summary_twd != calc_total_twd:
    errors.append(f'Summary TWD total mismatch: {summary_twd} vs {calc_total_twd}')
if missing_by_order:
    # Blank cells are allowed; report note must mention them.
    if wr['B9'].value != missing_notes:
        errors.append('Missing-data notes not written to Report!B9')
else:
    if '未缺資料' not in str(wr['B9'].value):
        errors.append('No-missing-data note not written to Report!B9')
if not OUT_SUMMARY.exists() or CUSTOMER_ID not in OUT_SUMMARY.read_text(encoding='utf-8'):
    errors.append('Summary text file missing or invalid')

print('\nVerification:')
print('Saved workbook:', OUT_XLSX)
print('Saved summary:', OUT_SUMMARY)
print('Details rows checked:', len(detailed))
print('Details headers checked:', actual_headers)
print('All CustomerID values:', sorted({wd.cell(r,2).value for r in range(5, wd.max_row+1)}))
print('All OrderIDs:', seen_oids)
print('Calculated Details NetAmountTWD total:', calc_total_twd)
print('Summary grouped row count:', ws.max_row - 4)
print('Summary total rows count:', summary_count)
print('Missing notes:', missing_notes)
if errors:
    print('ERRORS:')
    for e in errors:
        print('-', e)
    raise SystemExit(1)
print('All checks passed.')