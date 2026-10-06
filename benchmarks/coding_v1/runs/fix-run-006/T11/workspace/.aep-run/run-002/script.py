from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
import re
import openpyxl

BASE_LIST_URL = 'http://127.0.0.1:56996/t11/list'
OUT = Path('output')
OUT.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT / 'details.xlsx'

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._in_a = False
        self._href = None
        self._text = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            d = dict(attrs)
            self._in_a = True
            self._href = d.get('href')
            self._text = []
    def handle_data(self, data):
        if self._in_a:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self._in_a:
            self.links.append((self._href, ' '.join(''.join(self._text).split())))
            self._in_a = False
            self._href = None
            self._text = []

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens = []
        self.hrefs = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            href = dict(attrs).get('href')
            if href:
                self.hrefs.append(href)
    def handle_data(self, data):
        text = ' '.join(data.split())
        if text:
            self.tokens.append(text)

def fetch(url):
    with urlopen(url, timeout=10) as r:
        charset = r.headers.get_content_charset() or 'utf-8'
        return r.read().decode(charset, errors='replace')

def parse_links(html):
    p = LinkParser()
    p.feed(html)
    # keep product item links only, preserving order
    out = []
    seen = set()
    for href, text in p.links:
        if href and '/t11/item/' in href:
            url = urljoin(BASE_LIST_URL, href)
            if url not in seen:
                seen.add(url)
                out.append(url)
    return out

def parse_price_currency(value):
    if not value:
        return '', ''
    s = value.strip()
    # Examples handled: "$1,299", "USD 1299", "1299 USD", "EUR 899", "NT$ 1000"
    currency = ''
    if '$' in s:
        currency = '$'
    m = re.search(r'\b([A-Z]{3})\b', s)
    if m:
        currency = m.group(1)
    if '€' in s:
        currency = '€'
    if '£' in s:
        currency = '£'
    nums = re.findall(r'[-+]?\d[\d,]*(?:\.\d+)?', s)
    price = nums[0].replace(',', '') if nums else ''
    if price:
        try:
            f = float(price)
            price = int(f) if f.is_integer() else f
        except Exception:
            pass
    return price, currency

def memory_to_gb(value):
    if not value:
        return ''
    s = value.strip()
    m = re.search(r'([-+]?\d+(?:\.\d+)?)\s*([KMGT]?I?B|[KMGT])?', s, re.I)
    if not m:
        return ''
    num = float(m.group(1))
    unit = (m.group(2) or 'GB').upper()
    # Treat MB/GB/TB as decimal-ish product specs; MiB/GiB/TiB as binary. Output numeric GB.
    if unit in ('GB', 'G', 'GIB'):
        gb = num
    elif unit in ('MB', 'M'):
        gb = num / 1000.0
    elif unit == 'MIB':
        gb = num / 1024.0
    elif unit in ('KB', 'K'):
        gb = num / 1000_000.0
    elif unit == 'KIB':
        gb = num / (1024.0 * 1024.0)
    elif unit in ('TB', 'T'):
        gb = num * 1000.0
    elif unit == 'TIB':
        gb = num * 1024.0
    else:
        gb = num
    return int(gb) if abs(gb - round(gb)) < 1e-9 else gb

def normalize_key(k):
    return re.sub(r'[^a-z0-9]', '', k.lower())

def parse_detail(html, url):
    # Print sample text to make source structure visible during run.
    text_parser = TextParser()
    text_parser.feed(html)
    tokens = text_parser.tokens
    print('\nDetail URL:', url)
    print('Tokens:', tokens[:30])

    fields = {}
    # Parse table rows such as <tr><th>Name</th><td>...</td></tr> or definition-like text tokens.
    # Token sequence often contains alternating labels and values.
    wanted = {'name': 'Name', 'price': 'Price', 'currency': 'Currency', 'cpu': 'CPU', 'memory': 'MemoryGB', 'memorygb': 'MemoryGB'}
    for i, tok in enumerate(tokens):
        key = normalize_key(tok.rstrip(':'))
        if key in wanted and i + 1 < len(tokens):
            fields[wanted[key]] = tokens[i + 1]

    # Also inspect raw HTML for label/value pairs in table/list markup when token adjacency has extra separators.
    pairs = re.findall(r'<(?:th|dt|strong|span|div)[^>]*>\s*([^<:]+):?\s*</(?:th|dt|strong|span|div)>\s*<(?:td|dd|span|div)[^>]*>\s*([^<]+?)\s*</(?:td|dd|span|div)>', html, flags=re.I|re.S)
    for k, v in pairs:
        nk = normalize_key(re.sub('<[^>]+>', '', k).strip())
        if nk in wanted:
            fields[wanted[nk]] = ' '.join(re.sub('<[^>]+>', '', v).split())

    # Fallback regexes over visible text joined by newlines.
    visible = '\n'.join(tokens)
    for label, outkey in [('Name', 'Name'), ('CPU', 'CPU'), ('MemoryGB', 'MemoryGB'), ('Memory', 'MemoryGB'), ('Currency', 'Currency'), ('Price', 'Price')]:
        if outkey not in fields:
            m = re.search(rf'(?im)^{re.escape(label)}\s*:?\s*(.+)$', visible)
            if m:
                fields[outkey] = m.group(1).strip()

    price_raw = fields.get('Price', '')
    price, cur_from_price = parse_price_currency(price_raw)
    currency = fields.get('Currency', '') or cur_from_price
    if currency == '' and cur_from_price:
        currency = cur_from_price

    row = {
        'Name': fields.get('Name', ''),
        'Price': price if price != '' else '',
        'Currency': currency,
        'CPU': fields.get('CPU', ''),
        'MemoryGB': memory_to_gb(fields.get('MemoryGB', '')),
        'URL': url,
    }
    print('Parsed row:', row)
    return row

list_html = fetch(BASE_LIST_URL)
links = parse_links(list_html)
print('Product detail links found:', len(links), links)
rows = [parse_detail(fetch(u), u) for u in links]

headers = ['Name', 'Price', 'Currency', 'CPU', 'MemoryGB', 'URL']
wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'details'
ws.append(headers)
for row in rows:
    ws.append([row[h] for h in headers])
wb.save(OUT_FILE)
print('\nWrote', OUT_FILE)

# Verification: reopen the output and confirm stated requirements from saved file.
wb2 = openpyxl.load_workbook(OUT_FILE, data_only=True)
ws2 = wb2.active
read_headers = [c.value for c in ws2[1]]
assert read_headers == headers, f'headers mismatch: {read_headers}'
data_rows = list(ws2.iter_rows(min_row=2, values_only=True))
assert len(data_rows) == len(links), f'row count mismatch {len(data_rows)} != {len(links)}'
for idx, r in enumerate(data_rows, start=2):
    rec = dict(zip(headers, r))
    assert rec['URL'] in links, f'row {idx} URL not from detail links'
    # Required columns exist; missing fields may remain blank/None in xlsx.
    if rec['Price'] is not None:
        assert isinstance(rec['Price'], (int, float)), f'row {idx} Price not numeric: {rec["Price"]!r}'
    if rec['MemoryGB'] is not None:
        assert isinstance(rec['MemoryGB'], (int, float)), f'row {idx} MemoryGB not numeric: {rec["MemoryGB"]!r}'
    assert rec['URL'], f'row {idx} URL blank'
print('Verification passed: file details.xlsx exists; headers match; row count =', len(data_rows), '; Price/MemoryGB numeric when present; URL populated from detail pages.')
print('Saved rows:')
for r in data_rows:
    print(dict(zip(headers, r)))