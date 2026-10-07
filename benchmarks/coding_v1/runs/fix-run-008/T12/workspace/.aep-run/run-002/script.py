import csv
import os
import re
import urllib.request
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path

URLS = [
    'http://127.0.0.1:64650/t12/a',
    'http://127.0.0.1:64650/t12/b',
    'http://127.0.0.1:64650/t12/c',
]
FIELDS = ['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL']

class Node:
    def __init__(self, tag, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.parent = parent
        self.children = []
        self.text_parts = []
    def text(self):
        parts = list(self.text_parts)
        for child in self.children:
            parts.append(child.text())
        return ''.join(parts)
    def find_all(self, tag=None, attrs=None):
        attrs = attrs or {}
        out = []
        ok_tag = tag is None or self.tag == tag
        ok_attrs = all(self.attrs.get(k) == v for k, v in attrs.items())
        if ok_tag and ok_attrs:
            out.append(self)
        for child in self.children:
            out.extend(child.find_all(tag, attrs))
        return out
    def find_first(self, tag=None, attrs=None):
        found = self.find_all(tag, attrs)
        return found[0] if found else None

class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Node('document')
        self.current = self.root
    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        self.current = node
    def handle_endtag(self, tag):
        node = self.current
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root:
            self.current = node.parent
    def handle_data(self, data):
        self.current.text_parts.append(data)

def fetch(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        charset = r.headers.get_content_charset() or 'utf-8'
        return r.read().decode(charset, errors='replace')

def parse_html(html):
    parser = TreeParser()
    parser.feed(html)
    return parser.root

def clean_space(s):
    return re.sub(r'\s+', ' ', s).strip()

def parse_memory_to_gb(text):
    m = re.search(r'([0-9]+(?:[\.,][0-9]+)?)\s*(GB|MB)\b', text, flags=re.I)
    if not m:
        raise ValueError(f'Cannot parse memory: {text!r}')
    value = Decimal(m.group(1).replace(',', '.'))
    unit = m.group(2).upper()
    if unit == 'MB':
        value = value / Decimal(1024)
    return value

def parse_price_currency(text):
    s = clean_space(text)
    if 'NT$' in s:
        currency = 'NT$'
    elif re.search(r'\bUSD\b', s, flags=re.I):
        currency = 'USD'
    elif '€' in s:
        currency = 'EUR'
    else:
        raise ValueError(f'Cannot determine currency: {text!r}')

    amount = s.replace('NT$', '').replace('€', '')
    amount = re.sub(r'\bUSD\b', '', amount, flags=re.I).strip()
    amount = re.sub(r'[^0-9,\.]', '', amount)
    if not amount:
        raise ValueError(f'Cannot parse price: {text!r}')

    # Normalize thousands/decimal separators.
    if ',' in amount and '.' in amount:
        if amount.rfind(',') > amount.rfind('.'):
            # European form: 1.299,00 -> 1299.00
            normalized = amount.replace('.', '').replace(',', '.')
        else:
            # US form: 1,250.00 -> 1250.00
            normalized = amount.replace(',', '')
    elif ',' in amount:
        # Treat comma as thousands when exactly 3 digits follow; otherwise decimal comma.
        parts = amount.split(',')
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            normalized = ''.join(parts)
        else:
            normalized = amount.replace(',', '.')
    else:
        normalized = amount
    return Decimal(normalized), currency

def dec_to_text(d):
    # Keep plain numeric text, dropping unnecessary trailing zeros.
    if d == d.to_integral_value():
        return str(d.to_integral_value())
    return format(d.normalize(), 'f')

def parse_catalog(url, html):
    root = parse_html(html)
    rows = []
    if url.endswith('/a'):
        table = root.find_first('table', {'id': 'p'})
        if table is None:
            raise ValueError('Catalog A table #p not found')
        trs = table.find_all('tr')
        for tr in trs[1:]:
            tds = tr.find_all('td')
            if len(tds) < 3:
                continue
            model = clean_space(tds[0].text())
            price, currency = parse_price_currency(tds[1].text())
            mem_gb = parse_memory_to_gb(tds[2].text())
            rows.append({'Model': model, 'Price': price, 'Currency': currency, 'MemoryGB': mem_gb, 'SourceURL': url})
    elif url.endswith('/b'):
        for item in root.find_all('div', {'class': 'item'}):
            h2 = item.find_first('h2')
            price_node = item.find_first('p', {'class': 'price'})
            mem_node = item.find_first('p', {'class': 'mem'})
            if not (h2 and price_node and mem_node):
                continue
            model = clean_space(h2.text())
            price, currency = parse_price_currency(price_node.text())
            mem_gb = parse_memory_to_gb(mem_node.text())
            rows.append({'Model': model, 'Price': price, 'Currency': currency, 'MemoryGB': mem_gb, 'SourceURL': url})
    elif url.endswith('/c'):
        for li in root.find_all('li'):
            model = li.attrs.get('data-model') or clean_space(li.text()).split('—')[0].strip()
            text = clean_space(li.text())
            parts = [p.strip() for p in text.split('—')]
            if len(parts) >= 3:
                price_text, mem_text = parts[1], parts[2]
            else:
                price_text = text
                mem_text = text
            price, currency = parse_price_currency(price_text)
            mem_gb = parse_memory_to_gb(mem_text)
            rows.append({'Model': model, 'Price': price, 'Currency': currency, 'MemoryGB': mem_gb, 'SourceURL': url})
    else:
        raise ValueError(f'Unknown catalog URL layout: {url}')
    return rows

workspace = Path.cwd()
out_dir = workspace / 'output'
out_dir.mkdir(exist_ok=True)
out_file = out_dir / 'merged_catalog.csv'

all_rows = []
for url in URLS:
    html = fetch(url)
    parsed = parse_catalog(url, html)
    print(f'{url}: parsed {len(parsed)} rows')
    all_rows.extend(parsed)

with out_file.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=FIELDS)
    writer.writeheader()
    for r in all_rows:
        writer.writerow({
            'Model': r['Model'],
            'Price': dec_to_text(r['Price']),
            'Currency': r['Currency'],
            'MemoryGB': dec_to_text(r['MemoryGB']),
            'SourceURL': r['SourceURL'],
        })
print('wrote:', out_file)

# Verification: reopen the saved output and check stated requirements.
with out_file.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    saved = list(reader)
    assert reader.fieldnames == FIELDS, f'columns mismatch: {reader.fieldnames}'

assert len(saved) == 6, f'expected 6 rows from the three catalogs, got {len(saved)}'
expected = [
    ('NX-1', Decimal('12000'), 'NT$', Decimal('16'), URLS[0]),
    ('NX-2', Decimal('8500'), 'NT$', Decimal('8'), URLS[0]),
    ('NX-1', Decimal('399.5'), 'USD', Decimal('16'), URLS[1]),
    ('NX-3', Decimal('1250'), 'USD', Decimal('32'), URLS[1]),
    ('NX-4', Decimal('499'), 'EUR', Decimal('4'), URLS[2]),
    ('NX-5', Decimal('1299'), 'EUR', Decimal('64'), URLS[2]),
]
for i, (row, exp) in enumerate(zip(saved, expected), start=1):
    emodel, eprice, ecurrency, emem, eurl = exp
    assert row['Model'] == emodel, (i, row)
    assert Decimal(row['Price']) == eprice, (i, row)
    assert row['Currency'] == ecurrency, (i, row)
    assert Decimal(row['MemoryGB']) == emem, (i, row)
    assert row['SourceURL'] == eurl, (i, row)

# Confirm same model from different sources is retained.
nx1_rows = [r for r in saved if r['Model'] == 'NX-1']
assert len(nx1_rows) == 2 and nx1_rows[0]['SourceURL'] != nx1_rows[1]['SourceURL']

print('verification passed:')
print(' - file exists:', out_file)
print(' - columns:', FIELDS)
print(' - row count:', len(saved))
print(' - numeric Price and MemoryGB parsed successfully')
print(' - currencies retained without conversion')
print(' - duplicate model NX-1 retained as separate source rows')
for row in saved:
    print(row)
