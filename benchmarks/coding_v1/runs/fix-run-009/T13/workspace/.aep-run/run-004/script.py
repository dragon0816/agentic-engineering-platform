from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urljoin
import urllib.request, urllib.error
import json, re
from openpyxl import Workbook, load_workbook

WORKSPACE = Path.cwd()
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(parents=True, exist_ok=True)
LIST_URL = 'http://127.0.0.1:50351/t13/list'
XLSX_PATH = OUTPUT / 'robust_products.xlsx'
WARNINGS_PATH = OUTPUT / 'warnings.json'
HEADERS = ['Name', 'Price', 'Currency', 'CPU', 'URL', 'FetchStatus']
NA = 'N/A'

class ProductListParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.in_products = False
        self.depth = 0
        self.href = None
        self.text = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'ul' and attrs.get('id') == 'products':
            self.in_products = True
            self.depth = 1
        elif self.in_products:
            self.depth += 1
        if self.in_products and tag == 'a':
            self.href = attrs.get('href')
            self.text = []
    def handle_data(self, data):
        if self.href is not None:
            self.text.append(data)
    def handle_endtag(self, tag):
        if tag == 'a' and self.href is not None:
            name = ' '.join(''.join(self.text).split())
            if name and self.href:
                self.links.append((name, self.href))
            self.href = None
            self.text = []
        if self.in_products:
            self.depth -= 1
            if self.depth <= 0:
                self.in_products = False

class DetailParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.elements = []
        self.rows = []
        self.row = None
        self.cell = None
    def handle_starttag(self, tag, attrs):
        self.stack.append([tag.lower(), {k.lower(): v or '' for k, v in attrs}, []])
        if tag.lower() == 'tr':
            self.row = []
        if tag.lower() in ('td', 'th') and self.row is not None:
            self.cell = []
    def handle_data(self, data):
        for item in self.stack:
            item[2].append(data)
        if self.cell is not None:
            self.cell.append(data)
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('td', 'th') and self.cell is not None and self.row is not None:
            self.row.append(clean(''.join(self.cell)))
            self.cell = None
        if tag == 'tr' and self.row is not None:
            self.rows.append(self.row)
            self.row = None
        if self.stack:
            t, attrs, text_parts = self.stack.pop()
            text = clean(''.join(text_parts))
            if text:
                self.elements.append({'tag': t, 'attrs': attrs, 'text': text})

def clean(value):
    if value is None:
        return NA
    value = re.sub(r'\s+', ' ', str(value)).strip().strip(':：;')
    return value or NA

def fetch(url, retry_500=False, max_attempts=3):
    attempts = 0
    while attempts < (max_attempts if retry_500 else 1):
        attempts += 1
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'AEP-product-collector/1.0'})
            with urllib.request.urlopen(req, timeout=10) as r:
                return True, r.status, r.read().decode('utf-8', errors='replace'), attempts, None
        except urllib.error.HTTPError as e:
            err = f'HTTP {e.code}'
            try:
                e.read()
            except Exception:
                pass
            if retry_500 and e.code == 500 and attempts < max_attempts:
                continue
            return False, e.code, '', attempts, err
        except Exception as e:
            return False, None, '', attempts, f'{type(e).__name__}: {e}'

def parse_price(value):
    value = clean(value)
    if value == NA:
        return NA
    m = re.search(r'[-+]?\d[\d,]*(?:\.\d+)?', value)
    if not m:
        return NA
    s = m.group(0).replace(',', '')
    try:
        return float(s) if '.' in s else int(s)
    except ValueError:
        return NA

def parse_currency(value):
    value = clean(value)
    if value == NA:
        return NA
    # Longer/more specific symbols first.
    symbol_codes = [('NT$', 'TWD'), ('TWD', 'TWD'), ('USD', 'USD'), ('EUR', 'EUR'), ('JPY', 'JPY'), ('$', 'USD'), ('€', 'EUR'), ('£', 'GBP'), ('¥', 'JPY')]
    upper = value.upper()
    for token, code in symbol_codes:
        if token.upper() in upper:
            return code
    m = re.search(r'\b[A-Z]{3}\b', value)
    return m.group(0) if m else NA

def parse_detail(html, fallback_name):
    p = DetailParser()
    p.feed(html)
    fields = {}
    for row in p.rows:
        if len(row) >= 2:
            key = clean(row[0]).lower()
            fields[key] = clean(row[1])
    name = NA
    for e in p.elements:
        klass_id = (e['attrs'].get('class', '') + ' ' + e['attrs'].get('id', '')).lower()
        if e['tag'] in ('h1', 'h2') or 'name' in klass_id or 'title' in klass_id:
            name = clean(e['text'])
            break
    if name == NA:
        name = fallback_name
    price_raw = fields.get('price', NA)
    cpu = fields.get('cpu', fields.get('processor', fields.get('chipset', NA)))
    return {
        'Name': clean(name),
        'Price': parse_price(price_raw),
        'Currency': parse_currency(price_raw),
        'CPU': clean(cpu),
    }

ok, status, list_html, attempts, err = fetch(LIST_URL)
if not ok:
    raise RuntimeError(f'Could not fetch list: {err}')
lp = ProductListParser(); lp.feed(list_html)
products = lp.links[:5]
print('List products:', products)
if len(products) != 5:
    raise RuntimeError(f'Expected exactly five products, got {len(products)}')

rows = []
warnings = []
for list_name, href in products:
    url = urljoin(LIST_URL, href)
    ok, status, html, attempts, err = fetch(url, retry_500=True, max_attempts=3)
    if ok:
        data = parse_detail(html, list_name)
        row = {**data, 'URL': url, 'FetchStatus': 'ok'}
        warnings.append({'Name': row['Name'], 'URL': url, 'FetchStatus': 'ok', 'attempts': attempts, 'http_status': status})
    else:
        row = {'Name': list_name, 'Price': NA, 'Currency': NA, 'CPU': NA, 'URL': url, 'FetchStatus': 'error'}
        warnings.append({'Name': list_name, 'URL': url, 'FetchStatus': 'error', 'attempts': attempts, 'http_status': status, 'error': err})
    rows.append(row)
    print(row)

wb = Workbook()
ws = wb.active
ws.title = 'Products'
ws.append(HEADERS)
for row in rows:
    ws.append([row[h] for h in HEADERS])
wb.save(XLSX_PATH)

WARNINGS_PATH.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')

# Verification by reopening saved outputs.
wb2 = load_workbook(XLSX_PATH, data_only=True)
ws2 = wb2['Products']
assert [c.value for c in ws2[1]] == HEADERS
saved = [dict(zip(HEADERS, r)) for r in ws2.iter_rows(min_row=2, values_only=True)]
assert len(saved) == 5
for r in saved:
    assert r['Name'] and r['URL'] and r['FetchStatus'] in ('ok', 'error')
    assert r['Price'] is not None and r['Currency'] is not None and r['CPU'] is not None
    if r['FetchStatus'] == 'error':
        assert r['Price'] == NA and r['Currency'] == NA and r['CPU'] == NA
# Known missing/detail outcomes from source markup checked above.
by_name = {r['Name']: r for r in saved}
assert by_name['Phone C']['Price'] == NA and by_name['Phone C']['Currency'] == NA
assert by_name['Phone D']['CPU'] == NA
assert by_name['Phone E']['FetchStatus'] == 'error'
assert by_name['Phone E']['Price'] == by_name['Phone E']['Currency'] == by_name['Phone E']['CPU'] == NA
warn = json.loads(WARNINGS_PATH.read_text(encoding='utf-8'))
assert len(warn) == 5
assert all(w['FetchStatus'] in ('ok', 'error') for w in warn)
assert [w for w in warn if w['Name'] == 'Phone E'][0]['attempts'] == 3
assert all(w['FetchStatus'] == 'ok' for w in warn if w['Name'] != 'Phone E')

print('Wrote', XLSX_PATH)
print('Wrote', WARNINGS_PATH)
print('Verified: headers, row count 5, missing fields as N/A, Phone E retried 3 times and marked error, successful warnings set ok.')