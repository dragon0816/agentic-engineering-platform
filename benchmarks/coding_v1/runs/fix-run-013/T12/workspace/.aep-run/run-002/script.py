from pathlib import Path
from urllib.request import urlopen
from html.parser import HTMLParser
from decimal import Decimal
import csv
import re

workspace = Path.cwd()
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

urls = [
    'http://127.0.0.1:63795/t12/a',
    'http://127.0.0.1:63795/t12/b',
    'http://127.0.0.1:63795/t12/c',
]

class Node:
    def __init__(self, tag='root', attrs=None, parent=None):
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

class TreeParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Node()
        self.current = self.root
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.current)
        self.current.children.append(n)
        self.current = n
    def handle_endtag(self, tag):
        n = self.current
        while n.parent is not None:
            if n.tag == tag:
                self.current = n.parent
                return
            n = n.parent
    def handle_data(self, data):
        self.current.text_parts.append(data)

def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)

def has_class(node, class_name):
    return class_name in node.attrs.get('class', '').split()

def direct_children(node, tag=None):
    return [c for c in node.children if tag is None or c.tag == tag]

def fetch_tree(url):
    with urlopen(url, timeout=10) as resp:
        html = resp.read().decode('utf-8', errors='replace')
    parser = TreeParser()
    parser.feed(html)
    return parser.root, html

def parse_money(raw):
    s = raw.strip()
    if s.startswith('NT$'):
        currency = 'NT$'
        num = s[3:].strip()
        dec = Decimal(num.replace(',', ''))
    elif s.startswith('USD'):
        currency = 'USD'
        num = s[3:].strip()
        dec = Decimal(num.replace(',', ''))
    elif s.startswith('€'):
        currency = '€'
        num = s[1:].strip()
        # European samples use dot thousands and comma decimal when both appear.
        if ',' in num:
            num = num.replace('.', '').replace(',', '.')
        else:
            num = num.replace(',', '')
        dec = Decimal(num)
    else:
        m = re.match(r'([^\d.,+-]+)\s*([\d.,+-]+)', s)
        if not m:
            raise ValueError(f'Cannot parse money: {raw!r}')
        currency = m.group(1).strip()
        num = m.group(2).strip().replace(',', '')
        dec = Decimal(num)
    return currency, dec

def money_decimal_to_output(dec):
    # Numeric string without currency/thousands; keeps decimals only when needed.
    if dec == dec.to_integral_value():
        return str(int(dec))
    return format(dec.normalize(), 'f')

def parse_memory_gb(raw):
    s = raw.strip()
    m = re.search(r'([\d.]+)\s*(GB|MB)', s, flags=re.I)
    if not m:
        raise ValueError(f'Cannot parse memory: {raw!r}')
    value = Decimal(m.group(1))
    unit = m.group(2).upper()
    gb = value if unit == 'GB' else value / Decimal(1024)
    if gb == gb.to_integral_value():
        return str(int(gb))
    return format(gb.normalize(), 'f')

def parse_a(root, url):
    rows = []
    table = next((n for n in walk(root) if n.tag == 'table' and n.attrs.get('id') == 'p'), None)
    if table is None:
        raise ValueError('table#p not found')
    trs = [n for n in walk(table) if n.tag == 'tr']
    for tr in trs[1:]:
        cells = [c.text().strip() for c in direct_children(tr, 'td')]
        if len(cells) != 3:
            continue
        currency, price = parse_money(cells[1])
        rows.append({
            'Model': cells[0],
            'Price': money_decimal_to_output(price),
            'Currency': currency,
            'MemoryGB': parse_memory_gb(cells[2]),
            'SourceURL': url,
        })
    return rows

def parse_b(root, url):
    rows = []
    for item in [n for n in walk(root) if n.tag == 'div' and has_class(n, 'item')]:
        h2 = next((c for c in item.children if c.tag == 'h2'), None)
        price_node = next((c for c in item.children if c.tag == 'p' and has_class(c, 'price')), None)
        mem_node = next((c for c in item.children if c.tag == 'p' and has_class(c, 'mem')), None)
        if not (h2 and price_node and mem_node):
            continue
        currency, price = parse_money(price_node.text())
        rows.append({
            'Model': h2.text().strip(),
            'Price': money_decimal_to_output(price),
            'Currency': currency,
            'MemoryGB': parse_memory_gb(mem_node.text()),
            'SourceURL': url,
        })
    return rows

def parse_c(root, url):
    rows = []
    for li in [n for n in walk(root) if n.tag == 'li' and 'data-model' in n.attrs]:
        text = re.sub(r'\s+', ' ', li.text().strip())
        parts = [p.strip() for p in text.split('—')]
        if len(parts) != 3:
            raise ValueError(f'Unexpected catalog C row: {text!r}')
        model = li.attrs['data-model'].strip() or parts[0]
        currency, price = parse_money(parts[1])
        rows.append({
            'Model': model,
            'Price': money_decimal_to_output(price),
            'Currency': currency,
            'MemoryGB': parse_memory_gb(parts[2]),
            'SourceURL': url,
        })
    return rows

all_rows = []
for url in urls:
    root, html = fetch_tree(url)
    if url.endswith('/a'):
        rows = parse_a(root, url)
    elif url.endswith('/b'):
        rows = parse_b(root, url)
    elif url.endswith('/c'):
        rows = parse_c(root, url)
    else:
        raise ValueError(f'Unknown URL pattern: {url}')
    print(f'Parsed {len(rows)} rows from {url}')
    all_rows.extend(rows)

columns = ['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL']
out_csv = output_dir / 'catalog_products.csv'
with out_csv.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    writer.writerows(all_rows)
print('Wrote:', out_csv)
print('Rows:', len(all_rows))
for row in all_rows:
    print(row)

# Validation: reopen output, verify columns, row count, duplicate model preservation, numeric fields, and expected source URLs.
with out_csv.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    read_rows = list(reader)
    read_columns = reader.fieldnames

assert read_columns == columns, f'Columns mismatch: {read_columns}'
assert len(read_rows) == 6, f'Expected 6 rows, got {len(read_rows)}'
assert [r['Model'] for r in read_rows].count('NX-1') == 2, 'NX-1 from multiple sources was not preserved twice'
assert set(r['SourceURL'] for r in read_rows) == set(urls), 'SourceURL values mismatch'
for r in read_rows:
    Decimal(r['Price'])
    Decimal(r['MemoryGB'])
    assert r['Price'] == r['Price'].replace(',', ''), f'Price still has thousands separator: {r}'
    assert not any(sym in r['Price'] for sym in ['$', '€', 'NT', 'USD']), f'Price still has currency marker: {r}'
    assert r['Currency'] in {'NT$', 'USD', '€'}, f'Unexpected currency: {r}'
print('Validation OK: file name catalog_products.csv; columns exactly Model, Price, Currency, MemoryGB, SourceURL; 6 rows; Price and MemoryGB parse as numeric; duplicate model retained; SourceURL values preserved.')
