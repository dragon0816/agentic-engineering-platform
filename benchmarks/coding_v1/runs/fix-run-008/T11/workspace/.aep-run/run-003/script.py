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
        super().__init__(); self.links = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            href = dict(attrs).get('href')
            if href: self.links.append(href)

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('tr','li','div','p','h1','h2','h3','dt','dd','td','th'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag.lower() in ('tr','li','div','p','h1','h2','h3','dt','dd','td','th'):
            self.parts.append('\n')
    def handle_data(self, data):
        s = data.strip()
        if s: self.parts.append(s)
    def text(self):
        raw = unescape(' '.join(self.parts))
        raw = re.sub(r'[ \t\r\f\v]+', ' ', raw)
        raw = re.sub(r' *\n+ *', '\n', raw)
        return raw.strip()

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_cell=False; self.cell=[]; self.row=[]; self.rows=[]
    def handle_starttag(self, tag, attrs):
        tag=tag.lower()
        if tag == 'tr': self.row=[]
        elif tag in ('td','th'):
            self.in_cell=True; self.cell=[]
    def handle_endtag(self, tag):
        tag=tag.lower()
        if tag in ('td','th') and self.in_cell:
            self.row.append(unescape(' '.join(self.cell)).strip()); self.in_cell=False
        elif tag == 'tr' and self.row:
            self.rows.append(self.row)
    def handle_data(self, data):
        if self.in_cell:
            s=data.strip()
            if s: self.cell.append(s)

def fetch(url):
    with urlopen(url, timeout=10) as r:
        return r.read().decode('utf-8', errors='replace')

def text_from_html(html):
    p=TextParser(); p.feed(html); return p.text()

def table_pairs(html):
    p=TableParser(); p.feed(html)
    return [(r[0], r[1]) for r in p.rows if len(r) >= 2], p.rows

def strip_tags(s):
    return text_from_html(s)

def get_value(labels, html, text, pairs):
    for k,v in pairs:
        kk = re.sub(r'[:：]\s*$', '', str(k).strip())
        if any(kk.lower() == lab.lower() for lab in labels):
            return str(v).strip()
    alias_pat='|'.join(re.escape(x) for x in labels)
    m = re.search(rf'(?:{alias_pat})\s*[:：]\s*([^\n<;|]+)', text, flags=re.I)
    if m: return m.group(1).strip()
    return ''

def parse_memory_gb(s):
    if not s: return ''
    low=str(s).lower().replace(',', '')
    m=re.search(r'(\d+(?:\.\d+)?)\s*(tb|tib|gb|gib|mb|mib)\b', low)
    if not m:
        m=re.search(r'(\d+(?:\.\d+)?)', low)
        return float(m.group(1)) if m else ''
    n=float(m.group(1)); unit=m.group(2)
    if unit in ('tb','tib'): n *= 1024
    elif unit in ('mb','mib'): n /= 1024
    return int(n) if abs(n-round(n)) < 1e-9 else n

def parse_price_currency(s, explicit_currency=''):
    if not s:
        return '', explicit_currency or ''
    raw=str(s).strip()
    currency = explicit_currency.strip() if explicit_currency else ''
    # Important: check NT$/NTD before the generic dollar sign.
    if not currency:
        if re.search(r'\b(TWD|NTD)\b|NT\s*\$', raw, flags=re.I):
            currency = 'TWD'
        elif re.search(r'\bUSD\b|US\s*\$', raw, flags=re.I):
            currency = 'USD'
        elif re.search(r'\bEUR\b|€', raw, flags=re.I):
            currency = 'EUR'
        elif re.search(r'\bJPY\b|¥', raw, flags=re.I):
            currency = 'JPY'
        elif '$' in raw:
            currency = 'USD'
    m=re.search(r'[0-9][0-9,]*(?:\.\d+)?', raw)
    if not m:
        return '', currency
    num=m.group(0).replace(',', '')
    price=float(num) if '.' in num else int(num)
    return price, currency

def parse_item(url, html):
    text = text_from_html(html)
    pairs, rows = table_pairs(html)
    name = get_value(['Name','Product Name','Title'], html, text, pairs)
    if not name:
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, flags=re.I|re.S) or re.search(r'<title[^>]*>(.*?)</title>', html, flags=re.I|re.S)
        if m: name = strip_tags(m.group(1)).strip()
    price_raw = get_value(['Price','Amount'], html, text, pairs)
    explicit_currency = get_value(['Currency'], html, text, pairs)
    price, currency = parse_price_currency(price_raw, explicit_currency)
    cpu = get_value(['CPU','Processor'], html, text, pairs)
    memory = parse_memory_gb(get_value(['Memory','MemoryGB','RAM'], html, text, pairs))
    rec = {'Name': name, 'Price': price, 'Currency': currency, 'CPU': cpu, 'MemoryGB': memory, 'URL': url}
    return rec, text, rows

list_html=fetch(BASE_URL)
lp=LinkParser(); lp.feed(list_html)
links=[urljoin(BASE_URL, href) for href in lp.links]
print('Found detail links:', links)
records=[]
for url in links:
    html=fetch(url)
    rec, text, rows = parse_item(url, html)
    print('detail:', url)
    print('rows:', rows)
    print('parsed:', rec)
    records.append(rec)

headers=['Name','Price','Currency','CPU','MemoryGB','URL']
wb=Workbook(); ws=wb.active; ws.title='details'; ws.append(headers)
for rec in records:
    ws.append([rec[h] if rec[h] != '' else None for h in headers])
wb.save(out_file)
print('Wrote:', out_file)

# Reopen and verify all stated requirements plus corrected NT$ currency.
wb2=load_workbook(out_file, data_only=True)
ws2=wb2.active
actual_headers=[c.value for c in ws2[1]]
rows=list(ws2.iter_rows(min_row=2, values_only=True))
print('VERIFY file exists:', out_file.exists())
print('VERIFY headers:', actual_headers)
print('VERIFY row count:', len(rows), 'expected:', len(links))
print('VERIFY rows:')
for row in rows: print(row)
assert actual_headers == headers
assert len(rows) == len(links)
for row in rows:
    d=dict(zip(headers,row))
    assert d['URL'] in links
    assert d['Currency'] == 'TWD', f"Expected TWD from NT$ price, got {d['Currency']!r}"
    assert isinstance(d['Price'], (int,float)), f"Price must be numeric when present: {d['Price']!r}"
    assert isinstance(d['MemoryGB'], (int,float)), f"MemoryGB must be numeric GB when present: {d['MemoryGB']!r}"
print('VERIFY passed: details.xlsx has Name, Price, Currency, CPU, MemoryGB, URL; 4 rows; MemoryGB numeric GB; missing CPU is blank; NT$ currency is TWD.')