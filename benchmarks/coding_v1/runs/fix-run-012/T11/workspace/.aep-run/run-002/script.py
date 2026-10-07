from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
import re
from openpyxl import Workbook, load_workbook

BASE_LIST_URL = 'http://127.0.0.1:64212/t11/list'
OUT = Path('output') / 'details.xlsx'
COLUMNS = ['Name', 'Price', 'Currency', 'CPU', 'MemoryGB', 'URL']

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            attrs = dict(attrs)
            self._href = attrs.get('href')
            self._text = []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self._href is not None:
            self.links.append((self._href, ''.join(self._text).strip()))
            self._href = None
            self._text = []

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        s = data.strip()
        if s:
            self.parts.append(s)

def fetch(url):
    with urlopen(url, timeout=10) as r:
        return r.read().decode('utf-8', errors='replace')

def text_from_html(html):
    p = TextParser()
    p.feed(html)
    return '\n'.join(p.parts)

def parse_money(value):
    value = (value or '').strip()
    if not value:
        return '', ''
    # Supports: USD 1299, $1,299 USD, EUR 999, 1299 USD
    currency = ''
    m = re.search(r'\b(USD|EUR|TWD|JPY|CNY|GBP)\b|[$€¥£]', value, re.I)
    if m:
        tok = m.group(0).upper()
        currency = {'$': 'USD', '€': 'EUR', '¥': 'JPY', '£': 'GBP'}.get(tok, tok)
    nums = re.findall(r'[-+]?\d[\d,]*(?:\.\d+)?', value)
    price = ''
    if nums:
        num = nums[0].replace(',', '')
        price = float(num) if '.' in num else int(num)
    return price, currency

def parse_memory_gb(value):
    value = (value or '').strip()
    if not value:
        return ''
    m = re.search(r'([-+]?\d+(?:\.\d+)?)\s*(TB|GB|MB|G|M)?\b', value, re.I)
    if not m:
        return ''
    amount = float(m.group(1))
    unit = (m.group(2) or 'GB').upper()
    if unit == 'TB':
        gb = amount * 1024
    elif unit in ('MB', 'M'):
        gb = amount / 1024
    else:
        gb = amount
    return int(gb) if gb.is_integer() else gb

def fields_from_text(text):
    fields = {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Title may appear as first line before key-value rows.
    if lines:
        fields.setdefault('Name', lines[0])
    for line in lines:
        # Match "Key: value", "Key - value", etc.
        m = re.match(r'^(Name|Price|Currency|CPU|Memory(?:GB)?|RAM)\s*[:：\-]\s*(.*)$', line, re.I)
        if m:
            key = m.group(1).lower()
            val = m.group(2).strip()
            if key == 'memory' or key == 'memorygb' or key == 'ram':
                fields['Memory'] = val
            else:
                fields[key.capitalize() if key != 'cpu' else 'CPU'] = val
    return fields

def parse_detail(html, url):
    text = text_from_html(html)
    fields = fields_from_text(text)

    # Fallback regex against raw markup/text for common variants.
    def raw_field(names):
        for name in names:
            pat = re.compile(rf'{name}\s*</?[^>]*>\s*[:：]?\s*(?:</[^>]+>\s*)?([^<\n]+)', re.I)
            m = pat.search(html)
            if m:
                return re.sub(r'\s+', ' ', m.group(1)).strip()
        return ''

    name = fields.get('Name') or raw_field(['Name'])
    price_raw = fields.get('Price') or raw_field(['Price'])
    currency = fields.get('Currency') or raw_field(['Currency'])
    cpu = fields.get('CPU') or raw_field(['CPU'])
    memory_raw = fields.get('Memory') or raw_field(['MemoryGB', 'Memory', 'RAM'])

    price, parsed_currency = parse_money(price_raw)
    if not currency:
        currency = parsed_currency
    return {
        'Name': name,
        'Price': price,
        'Currency': currency,
        'CPU': cpu,
        'MemoryGB': parse_memory_gb(memory_raw),
        'URL': url,
    }

print('workspace:', Path.cwd())
print('input files:', [p.name for p in Path('input').glob('*')])
list_html = fetch(BASE_LIST_URL)
print('list URL:', BASE_LIST_URL)
print('list markup first 1000 chars:')
print(list_html[:1000])
link_parser = LinkParser()
link_parser.feed(list_html)
links = [(urljoin(BASE_LIST_URL, href), text) for href, text in link_parser.links]
print('detail links found:', len(links), links)

rows = []
for i, (url, link_text) in enumerate(links, 1):
    html = fetch(url)
    print(f'detail {i} URL:', url)
    print('detail markup first 800 chars:')
    print(html[:800])
    row = parse_detail(html, url)
    if not row['Name']:
        row['Name'] = link_text
    rows.append(row)

OUT.parent.mkdir(parents=True, exist_ok=True)
wb = Workbook()
ws = wb.active
ws.title = 'details'
ws.append(COLUMNS)
for row in rows:
    ws.append([row[c] for c in COLUMNS])
wb.save(OUT)
print('wrote:', OUT)

# Verification by reopening saved output.
wb2 = load_workbook(OUT, data_only=True)
ws2 = wb2['details']
headers = [cell.value for cell in ws2[1]]
records = []
for r in ws2.iter_rows(min_row=2, values_only=True):
    records.append(dict(zip(headers, r)))
print('verify headers:', headers)
print('verify row count:', len(records))
print('verify records:')
for rec in records:
    print(rec)
assert headers == COLUMNS, f'headers mismatch: {headers}'
assert len(records) == len(links), f'row count mismatch: {len(records)} vs {len(links)}'
for rec in records:
    assert rec['URL'] and str(rec['URL']).startswith('http://127.0.0.1:64212/t11/item/'), rec
    if rec['Price'] is not None:
        assert isinstance(rec['Price'], (int, float)), f'Price not numeric: {rec}'
    if rec['MemoryGB'] is not None:
        assert isinstance(rec['MemoryGB'], (int, float)), f'MemoryGB not numeric: {rec}'
print('verification passed: output file reopened; required columns, row count, numeric Price/MemoryGB where present, blank missing fields, and URLs checked.')