from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
from html import unescape
import re
from openpyxl import Workbook, load_workbook

BASE_URL = 'http://127.0.0.1:64650/t11/list'
workspace = Path.cwd()
out_dir = workspace / 'output'
out_dir.mkdir(exist_ok=True)
out_file = out_dir / 'details.xlsx'

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            attrs = dict(attrs)
            href = attrs.get('href')
            if href:
                self.links.append(href)

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('tr','li','div','p','h1','h2','h3','dt','dd'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag.lower() in ('tr','li','div','p','h1','h2','h3','dt','dd','td','th'):
            self.parts.append('\n')
    def handle_data(self, data):
        data = data.strip()
        if data:
            self.parts.append(data)
    def text(self):
        raw = unescape(' '.join(self.parts))
        raw = re.sub(r'[ \t\r\f\v]+', ' ', raw)
        raw = re.sub(r' *\n+ *', '\n', raw)
        return raw.strip()

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_td = False
        self.in_th = False
        self.cell = []
        self.row = []
        self.rows = []
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == 'tr':
            self.row = []
        elif tag in ('td','th'):
            self.in_td = tag == 'td'
            self.in_th = tag == 'th'
            self.cell = []
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('td','th') and (self.in_td or self.in_th):
            self.row.append(unescape(' '.join(self.cell)).strip())
            self.in_td = self.in_th = False
        elif tag == 'tr':
            if self.row:
                self.rows.append(self.row)
    def handle_data(self, data):
        if self.in_td or self.in_th:
            s = data.strip()
            if s:
                self.cell.append(s)

def fetch(url):
    with urlopen(url, timeout=10) as r:
        return r.read().decode('utf-8', errors='replace')

def text_from_html(html):
    p = TextParser(); p.feed(html); return p.text()

def tables_from_html(html):
    p = TableParser(); p.feed(html); return p.rows

def strip_tags_fragment(fragment):
    return text_from_html(fragment)

def parse_memory_gb(value):
    if value is None:
        return ''
    s = str(value).strip()
    if not s:
        return ''
    low = s.lower().replace(',', '')
    m = re.search(r'(\d+(?:\.\d+)?)\s*(tb|tib|gb|gib|mb|mib)\b', low)
    if not m:
        m = re.search(r'(\d+(?:\.\d+)?)', low)
        if not m:
            return ''
        return float(m.group(1))
    n = float(m.group(1)); unit = m.group(2)
    if unit in ('tb','tib'):
        n *= 1024
    elif unit in ('mb','mib'):
        n /= 1024
    if abs(n - round(n)) < 1e-9:
        return int(round(n))
    return n

def get_labeled_value(label, html, text, table_pairs):
    # Prefer structured table/dl-like two column pairs.
    aliases = {
        'Name': ['Name', 'Product Name', 'Title'],
        'Price': ['Price', 'Amount'],
        'Currency': ['Currency'],
        'CPU': ['CPU', 'Processor'],
        'MemoryGB': ['Memory', 'MemoryGB', 'RAM']
    }[label]
    alias_pat = '|'.join(re.escape(a) for a in aliases)
    for k, v in table_pairs:
        kk = re.sub(r'[:：]\s*$', '', str(k).strip())
        if any(kk.lower() == a.lower() for a in aliases):
            return str(v).strip()
    # meta/data attributes or simple label:value in HTML/text
    patterns = [
        rf'(?:{alias_pat})\s*[:：]\s*([^\n<;|]+)',
        rf'<[^>]*(?:class|id|data-key)=["\'][^"\']*(?:{alias_pat})[^"\']*["\'][^>]*>(.*?)</[^>]+>',
    ]
    for pat in patterns:
        for source in (text, html):
            mo = re.search(pat, source, flags=re.I|re.S)
            if mo:
                val = strip_tags_fragment(mo.group(1)).strip()
                val = re.sub(r'\s+', ' ', val).strip()
                if val:
                    return val
    return ''

def parse_item(url, html):
    text = text_from_html(html)
    rows = tables_from_html(html)
    pairs = []
    for row in rows:
        if len(row) >= 2:
            pairs.append((row[0], row[1]))
    # Include definition/list structures and JSON-ish fragments.
    for key, val in re.findall(r'<(?:dt|span|div|strong|b)[^>]*>\s*([^<:：]{1,40})\s*[:：]?\s*</(?:dt|span|div|strong|b)>\s*<(?:dd|span|div)[^>]*>\s*(.*?)\s*</(?:dd|span|div)>', html, flags=re.I|re.S):
        pairs.append((strip_tags_fragment(key), strip_tags_fragment(val)))
    record = {'Name':'', 'Price':'', 'Currency':'', 'CPU':'', 'MemoryGB':'', 'URL':url}
    for field in ('Name','Price','Currency','CPU'):
        record[field] = get_labeled_value(field, html, text, pairs)
    memory_raw = get_labeled_value('MemoryGB', html, text, pairs)
    record['MemoryGB'] = parse_memory_gb(memory_raw)
    # fallback name from h1/title or first non-empty text line
    if not record['Name']:
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, flags=re.I|re.S)
        if not m:
            m = re.search(r'<title[^>]*>(.*?)</title>', html, flags=re.I|re.S)
        if m:
            record['Name'] = strip_tags_fragment(m.group(1)).strip()
        else:
            lines = [ln.strip() for ln in text.split('\n') if ln.strip()]
            if lines:
                record['Name'] = lines[0]
    # fallback price/currency from currency amount combos
    if not record['Price'] or not record['Currency']:
        m = re.search(r'\b(USD|EUR|TWD|NTD|JPY|CNY|GBP)\b\s*\$?\s*([0-9][0-9,]*(?:\.\d+)?)', text, flags=re.I)
        if not m:
            m2 = re.search(r'([$€¥])\s*([0-9][0-9,]*(?:\.\d+)?)', text)
            if m2:
                symmap = {'$':'USD','€':'EUR','¥':'JPY'}
                if not record['Currency']:
                    record['Currency'] = symmap.get(m2.group(1), m2.group(1))
                if not record['Price']:
                    record['Price'] = m2.group(2).replace(',', '')
        else:
            if not record['Currency']:
                record['Currency'] = m.group(1).upper()
            if not record['Price']:
                record['Price'] = m.group(2).replace(',', '')
    # numeric-clean price, but leave blank if absent
    if record['Price']:
        pm = re.search(r'[0-9][0-9,]*(?:\.\d+)?', str(record['Price']))
        record['Price'] = float(pm.group(0).replace(',', '')) if pm and '.' in pm.group(0) else (int(pm.group(0).replace(',', '')) if pm else record['Price'])
    return record, text, rows

# Fetch list and detail pages
list_html = fetch(BASE_URL)
link_parser = LinkParser(); link_parser.feed(list_html)
links = [urljoin(BASE_URL, href) for href in link_parser.links]
print('Found detail links:', links)

records = []
for i, url in enumerate(links, 1):
    html = fetch(url)
    record, text, rows = parse_item(url, html)
    print(f'--- detail {i}: {url}')
    print('html sample:', html[:800].replace('\n',' '))
    print('text:', text[:800])
    print('table rows:', rows[:10])
    print('parsed:', record)
    records.append(record)

headers = ['Name','Price','Currency','CPU','MemoryGB','URL']
wb = Workbook()
ws = wb.active
ws.title = 'details'
ws.append(headers)
for rec in records:
    ws.append([rec.get(h, '') for h in headers])
wb.save(out_file)
print('Wrote:', out_file)

# Verification: reopen output and confirm stated requirements.
wb2 = load_workbook(out_file, data_only=True)
ws2 = wb2.active
actual_headers = [c.value for c in ws2[1]]
rows = list(ws2.iter_rows(min_row=2, values_only=True))
print('VERIFY file exists:', out_file.exists())
print('VERIFY headers:', actual_headers)
print('VERIFY row count:', len(rows), 'expected:', len(links))
print('VERIFY rows:')
for row in rows:
    print(row)
assert actual_headers == headers, f'Header mismatch: {actual_headers}'
assert len(rows) == len(links), f'Row count mismatch {len(rows)} vs {len(links)}'
for row in rows:
    rec = dict(zip(headers, row))
    assert rec['URL'] in links, f"Unexpected URL {rec['URL']}"
    if rec['MemoryGB'] is not None:
        assert isinstance(rec['MemoryGB'], (int, float)), f"MemoryGB not numeric/blank: {rec['MemoryGB']!r}"
    if rec['Price'] is not None:
        assert isinstance(rec['Price'], (int, float)), f"Price not numeric/blank: {rec['Price']!r}"
print('VERIFY passed: details.xlsx has requested columns, one row per detail link, numeric Price/MemoryGB when present, blanks for missing cells.')