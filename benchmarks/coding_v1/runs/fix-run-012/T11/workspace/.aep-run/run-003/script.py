from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
import html as html_lib
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
            self._href = dict(attrs).get('href')
            self._text = []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self._href is not None:
            self.links.append((self._href, ''.join(self._text).strip()))
            self._href = None
            self._text = []

def fetch(url):
    with urlopen(url, timeout=10) as r:
        return r.read().decode('utf-8', errors='replace')

def strip_tags(fragment):
    text = re.sub(r'<[^>]*>', ' ', fragment)
    text = html_lib.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()

def parse_money(value):
    value = (value or '').strip()
    if not value:
        return '', ''
    upper = value.upper()
    currency = ''
    if 'NT$' in upper or 'TWD' in upper or 'NTD' in upper:
        currency = 'TWD'
    elif 'USD' in upper or re.search(r'(?<!NT)\$', value):
        currency = 'USD'
    elif 'EUR' in upper or '€' in value:
        currency = 'EUR'
    elif 'JPY' in upper or '¥' in value:
        currency = 'JPY'
    elif 'GBP' in upper or '£' in value:
        currency = 'GBP'
    elif 'CNY' in upper or 'RMB' in upper:
        currency = 'CNY'
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

def parse_detail(html, url, fallback_name=''):
    h1 = re.search(r'<h1\b[^>]*>(.*?)</h1>', html, re.I | re.S)
    title = re.search(r'<title\b[^>]*>(.*?)</title>', html, re.I | re.S)
    name = strip_tags(h1.group(1)) if h1 else (strip_tags(title.group(1)) if title else fallback_name)

    specs = {}
    for th, td in re.findall(r'<tr\b[^>]*>\s*<th\b[^>]*>(.*?)</th>\s*<td\b[^>]*>(.*?)</td>\s*</tr>', html, re.I | re.S):
        key = strip_tags(th).lower().replace(' ', '')
        val = strip_tags(td)
        specs[key] = val

    # Additional fallback for key:value text if table is absent.
    if not specs:
        text = strip_tags(html)
        for key in ['Price', 'Currency', 'CPU', 'Memory', 'MemoryGB', 'RAM']:
            m = re.search(rf'\b{key}\b\s*[:：\-]\s*([^:：\-]+?)(?=\s+(?:Price|Currency|CPU|Memory|MemoryGB|RAM)\b\s*[:：\-]|$)', text, re.I)
            if m:
                specs[key.lower()] = m.group(1).strip()

    price_raw = specs.get('price', '')
    price, parsed_currency = parse_money(price_raw)
    currency = specs.get('currency', '') or parsed_currency
    memory_raw = specs.get('memorygb', '') or specs.get('memory', '') or specs.get('ram', '')

    return {
        'Name': name,
        'Price': price,
        'Currency': currency,
        'CPU': specs.get('cpu', ''),
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
    detail_html = fetch(url)
    print(f'detail {i} URL:', url)
    print('detail markup first 800 chars:')
    print(detail_html[:800])
    row = parse_detail(detail_html, url, link_text)
    print('parsed row:', row)
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
records = [dict(zip(headers, r)) for r in ws2.iter_rows(min_row=2, values_only=True)]
print('verify headers:', headers)
print('verify row count:', len(records))
print('verify records:')
for rec in records:
    print(rec)

assert headers == COLUMNS, f'headers mismatch: {headers}'
assert len(records) == len(links), f'row count mismatch: {len(records)} vs {len(links)}'
for rec, source in zip(records, rows):
    for col in COLUMNS:
        got = rec[col]
        exp = source[col]
        if exp == '':
            assert got is None, f'{col} expected blank saved as None, got {got!r}'
        else:
            assert got == exp, f'{col} mismatch: saved {got!r}, expected {exp!r}'
    assert rec['Name'], f'Name missing: {rec}'
    assert rec['Price'] is None or isinstance(rec['Price'], (int, float)), f'Price not numeric/blank: {rec}'
    assert rec['MemoryGB'] is None or isinstance(rec['MemoryGB'], (int, float)), f'MemoryGB not numeric/blank: {rec}'
    assert rec['URL'] and str(rec['URL']).startswith('http://127.0.0.1:64212/t11/item/'), rec
print('verification passed: output file reopened; exact headers, 4 detail rows, parsed values, numeric Price/MemoryGB where present, blank missing CPU for Mini PC, and URLs checked.')