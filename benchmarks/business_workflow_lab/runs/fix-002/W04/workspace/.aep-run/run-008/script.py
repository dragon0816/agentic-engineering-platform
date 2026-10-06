from pathlib import Path
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode, urljoin
from http.cookiejar import CookieJar
from html.parser import HTMLParser
import csv, io, re, html as html_lib
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from copy import copy
from openpyxl import load_workbook

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
BASE = 'http://127.0.0.1:8810/'
FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
STATUS = 'Open'
NOW = '2026-10-06T00:00:00+08:00'  # supplied environment date

# ---------- HTTP client with SSO recovery ----------
class ERPClient:
    def __init__(self, base):
        self.base = base
        self.cj = CookieJar()
        self.opener = build_opener(HTTPCookieProcessor(self.cj))
        self.relogin_count = 0
        self.max_relogin = 3
        self.login('/orders')
    def _open(self, path, data=None):
        url = urljoin(self.base, path)
        req = Request(url, data=urlencode(data).encode('utf-8') if data is not None else None,
                      method='POST' if data is not None else 'GET')
        resp = self.opener.open(req, timeout=10)
        raw = resp.read()
        charset = 'utf-8'
        text = raw.decode(charset, errors='replace')
        return text, resp.geturl(), resp.headers.get('content-type','')
    def is_login_page(self, text, final_url):
        return ('<h1>Sign in</h1>' in text or "id='login-form'" in text or '/login' in final_url)
    def login(self, next_path):
        # Do not type credentials; use documented SSO button POST values.
        text, final_url, ctype = self._open('/login', {'next': next_path, 'sso': 'company'})
        if self.is_login_page(text, final_url):
            raise RuntimeError('SSO login did not leave login page')
        return text
    def get(self, path):
        text, final_url, ctype = self._open(path)
        if self.is_login_page(text, final_url):
            if self.relogin_count >= self.max_relogin:
                raise RuntimeError(f'工作階段恢復超過 {self.max_relogin} 次仍回到登入頁；last_url={final_url}')
            self.relogin_count += 1
            print(f'Re-login recovery {self.relogin_count}/{self.max_relogin} for {path}')
            self.login(path)
            text, final_url, ctype = self._open(path)
            if self.is_login_page(text, final_url):
                raise RuntimeError(f'重新登入後仍為登入頁；last_url={final_url}')
        return text, final_url, ctype

# ---------- parsers ----------
class HeaderParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_header = False
        self.in_tr = False
        self.cell_tag = None
        self.current = []
        self.rows = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table' and attrs.get('id') == 'header':
            self.in_header = True
        elif self.in_header and tag == 'tr':
            self.in_tr = True; self.current = []
        elif self.in_header and self.in_tr and tag in ('th','td'):
            self.cell_tag = tag; self._buf = []
    def handle_data(self, data):
        if self.in_header and self.in_tr and self.cell_tag:
            self._buf.append(data)
    def handle_endtag(self, tag):
        if self.in_header and self.in_tr and self.cell_tag == tag:
            self.current.append(''.join(self._buf).strip())
            self.cell_tag = None
        elif self.in_header and tag == 'tr':
            if len(self.current) >= 2:
                self.rows.append(self.current[:2])
            self.in_tr = False
        elif self.in_header and tag == 'table':
            self.in_header = False

class ResultCountParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_count=False; self.text=[]
    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        if attrs.get('id')=='result-count': self.in_count=True
    def handle_data(self, data):
        if self.in_count: self.text.append(data)
    def handle_endtag(self, tag):
        if self.in_count and tag=='p': self.in_count=False


def parse_header(html):
    p = HeaderParser(); p.feed(html)
    return {k: v for k, v in p.rows}

def parse_total(html):
    p=ResultCountParser(); p.feed(html)
    s=' '.join(''.join(p.text).split())
    m=re.search(r'Total:\s*(\d+)\s*rows', s)
    return int(m.group(1)) if m else None

# ---------- read source sample / get data ----------
client = ERPClient(BASE)
query = urlencode({'from': FROM_DATE, 'to': TO_DATE, 'status': STATUS, 'sort': 'OrderDate', 'dir': 'asc'})
list_html, _, _ = client.get('/orders?' + query)
total = parse_total(list_html)
print('Filtered list total from page:', total)

csv_text, _, ctype = client.get('/orders/export.csv?' + query)
if not ctype.lower().startswith('text/csv'):
    raise RuntimeError('Export did not return CSV content-type: ' + ctype)
reader = csv.DictReader(io.StringIO(csv_text.lstrip('\ufeff')))
orders = []
for row in reader:
    if not any((v or '').strip() for v in row.values()):
        continue
    # Normalize fieldnames if BOM remained
    row = {k.lstrip('\ufeff'): (v or '') for k,v in row.items()}
    orders.append(row)
print('CSV exported rows:', len(orders))
print('CSV headers:', reader.fieldnames)
print('First CSV rows:', orders[:3])
if total is not None and len(orders) != total:
    raise RuntimeError(f'CSV row count {len(orders)} != list total {total}')

# Verify filters and duplicates
seen=set()
for row in orders:
    oid=row['OrderID']
    if oid in seen:
        raise RuntimeError('Duplicate OrderID from export: '+oid)
    seen.add(oid)
    if not (FROM_DATE <= row['OrderDate'] <= TO_DATE and row['Status'] == STATUS):
        raise RuntimeError('Row outside requested filter: '+repr(row))

# Fetch details for every order; keep already obtained dicts to avoid duplicate work.
details = {}
for row in orders:
    oid = row['OrderID']
    if oid in details:
        continue
    html, _, _ = client.get('/orders/' + oid)
    hdr = parse_header(html)
    if hdr.get('OrderID') != oid:
        raise RuntimeError(f'Detail page mismatch for {oid}: got {hdr.get("OrderID")}')
    details[oid] = hdr
print('Detail pages fetched:', len(details), 're-login recoveries:', client.relogin_count)
print('Detail sample:', {k: details[k] for k in list(details)[:2]})

# Read FX rates (first two columns only; Note can contain commas in synthetic file)
rates = {}
with (INPUT/'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    r = csv.reader(f)
    header = next(r)
    for row in r:
        if len(row) >= 2 and row[0]:
            rates[row[0]] = Decimal(row[1])
print('FX rates:', rates)

# ---------- fill workbook ----------
template = INPUT / 'sales_template.xlsx'
outfile = OUTPUT / 'sales_2026_09_open_orders.xlsx'
wb = load_workbook(template)
wsd = wb['Details']; wsr = wb['Report']; wss = wb['Summary']

# Clear old data (if any), preserving sheets/headers. Delete rows below headers then add needed rows.
def clear_from(ws, start_row):
    if ws.max_row >= start_row:
        ws.delete_rows(start_row, ws.max_row - start_row + 1)
clear_from(wsd, 5)
clear_from(wss, 5)

# Report metadata
wsr['B3'] = FROM_DATE
wsr['D3'] = TO_DATE
wsr['B4'] = 'Sales Orders: Status=Open; OrderDate 2026-09-01..2026-09-30; sorted by OrderDate asc; detail fields CustomerContact and PaymentTerms fetched per OrderID'
wsr['B5'] = NOW
wsr['B7'] = 'Lab ERP (synthetic) Sales Orders'
wsr['D7'] = NOW
wsr['B9'] = f'{len(orders)} orders exported; {len(details)} detail pages fetched; session re-login recoveries: {client.relogin_count}; no duplicate OrderID.'

# Preserve style from row 5 if template had, otherwise row 4
style_source_row_details = 5 if wsd.max_row >= 5 else 4
for idx, row in enumerate(orders, start=5):
    oid = row['OrderID']
    hdr = details[oid]
    currency = row['Currency']
    amount = Decimal(row['NetAmount'])
    if currency not in rates:
        raise RuntimeError('Missing FX rate for '+currency)
    twd = (amount * rates[currency]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    values = [
        oid, row['CustomerID'], row['CustomerName'], row['ProjectID'], row['OrderDate'], row['Status'],
        currency, float(amount), float(twd), hdr.get('CustomerContact',''), hdr.get('PaymentTerms','')
    ]
    for col, val in enumerate(values, start=1):
        cell = wsd.cell(idx, col, val)
        # IDs and date as text as requested by format; amounts numeric.
        if col in (1,2,3,4,5,6,7,10,11):
            cell.number_format = '@'
        elif col in (8,9):
            cell.number_format = '0.00'

# Summary grouped by Status + Currency (all requested orders are Open, grouped by currency)
summary = {}
for row in orders:
    key = (row['Status'], row['Currency'])
    amount = Decimal(row['NetAmount'])
    twd = (amount * rates[row['Currency']]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    if key not in summary:
        summary[key] = {'amount': Decimal('0'), 'twd': Decimal('0'), 'count': 0}
    summary[key]['amount'] += amount
    summary[key]['twd'] += twd
    summary[key]['count'] += 1

for r_idx, ((status, currency), agg) in enumerate(sorted(summary.items(), key=lambda kv: (kv[0][0], kv[0][1])), start=5):
    vals = ['Status', status, currency, float(agg['amount'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), float(agg['twd'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)), agg['count']]
    for col, val in enumerate(vals, start=1):
        cell = wss.cell(r_idx, col, val)
        if col in (4,5): cell.number_format = '0.00'
        elif col == 6: cell.number_format = '0'
        else: cell.number_format = '@'

last_detail = 4 + len(orders)
if len(orders) > 0:
    wss['B2'] = f'=SUM(Details!I5:I{last_detail})'
else:
    wss['B2'] = '=SUM(Details!I5:I5)'
wss['B2'].number_format = '0.00'

# Keep ID/date columns as text at worksheet level where possible; set widths for readability
for col in ['A','B','D','E']:
    for cell in wsd[col][4:]:
        cell.number_format = '@'
for col in ['H','I']:
    for cell in wsd[col][4:]:
        cell.number_format = '0.00'
for col in ['D','E']:
    for cell in wss[col][4:]: cell.number_format='0.00'

wb.save(outfile)
print('Wrote', outfile)

# ---------- verification by reopening saved output ----------
wb2 = load_workbook(outfile, data_only=False)
wsd2 = wb2['Details']; wss2=wb2['Summary']; wsr2=wb2['Report']
headers = [wsd2.cell(4,c).value for c in range(1,12)]
expected_headers = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount','NetAmountTWD','CustomerContact','PaymentTerms']
assert headers == expected_headers, headers
rows = list(wsd2.iter_rows(min_row=5, max_row=wsd2.max_row, max_col=11, values_only=False)) if len(orders) else []
assert len(rows) == len(orders), (len(rows), len(orders))
ids = [r[0].value for r in rows]
assert len(ids) == len(set(ids)) == len(orders)
assert ids == [o['OrderID'] for o in orders]
for r in rows:
    vals=[c.value for c in r]
    assert isinstance(vals[0], str) and vals[0].startswith('00'), vals
    assert vals[4] >= FROM_DATE and vals[4] <= TO_DATE, vals
    assert vals[5] == STATUS, vals
    assert vals[9] not in (None,''), vals
    assert vals[10] not in (None,''), vals
    assert isinstance(vals[7], (int,float)) and isinstance(vals[8], (int,float)), vals
    cur=vals[6]; expected=(Decimal(str(vals[7]))*rates[cur]).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    assert Decimal(str(vals[8])).quantize(Decimal('0.01')) == expected, (vals, expected)
assert wsr2['B3'].value == FROM_DATE and wsr2['D3'].value == TO_DATE
assert wss2['B2'].value == f'=SUM(Details!I5:I{last_detail})'
summary_rows = list(wss2.iter_rows(min_row=5, max_row=wss2.max_row, max_col=6, values_only=True))
assert len(summary_rows) == len(summary)
assert sum(r[5] for r in summary_rows) == len(orders)
print('VERIFIED output workbook')
print('Details row count:', len(rows))
print('OrderIDs:', ids)
print('Summary rows:', summary_rows)
print('Formula Summary!B2:', wss2['B2'].value)
print('Report B9:', wsr2['B9'].value)
