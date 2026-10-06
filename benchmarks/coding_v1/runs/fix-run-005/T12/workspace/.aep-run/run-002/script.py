from pathlib import Path
from urllib.request import urlopen
from html.parser import HTMLParser
import csv
import re

WORKSPACE = Path.cwd()
OUTPUT_DIR = WORKSPACE / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

URLS = [
    'http://127.0.0.1:49758/t12/a',
    'http://127.0.0.1:49758/t12/b',
    'http://127.0.0.1:49758/t12/c',
]

class SimpleHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.tables = []
        self._current_table = None
        self._current_row = None
        self._current_cell = None
        self.items = []
        self._current_item = None
        self._capture_h2 = False
        self._capture_price = False
        self._capture_mem = False
        self.li = []
        self._current_li = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append((tag, attrs))
        if tag == 'table':
            self._current_table = []
        elif tag == 'tr' and self._current_table is not None:
            self._current_row = []
        elif tag in ('td', 'th') and self._current_row is not None:
            self._current_cell = ''
        elif tag == 'div' and attrs.get('class') == 'item':
            self._current_item = {'model': '', 'price': '', 'memory': ''}
        elif tag == 'h2' and self._current_item is not None:
            self._capture_h2 = True
        elif tag == 'p' and self._current_item is not None and attrs.get('class') == 'price':
            self._capture_price = True
        elif tag == 'p' and self._current_item is not None and attrs.get('class') == 'mem':
            self._capture_mem = True
        elif tag == 'li':
            self._current_li = {'attrs': attrs, 'text': ''}

    def handle_data(self, data):
        if self._current_cell is not None:
            self._current_cell += data
        if self._capture_h2:
            self._current_item['model'] += data
        if self._capture_price:
            self._current_item['price'] += data
        if self._capture_mem:
            self._current_item['memory'] += data
        if self._current_li is not None:
            self._current_li['text'] += data

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._current_cell is not None:
            self._current_row.append(self._current_cell.strip())
            self._current_cell = None
        elif tag == 'tr' and self._current_row is not None:
            self._current_table.append(self._current_row)
            self._current_row = None
        elif tag == 'table' and self._current_table is not None:
            self.tables.append(self._current_table)
            self._current_table = None
        elif tag == 'h2':
            self._capture_h2 = False
        elif tag == 'p':
            self._capture_price = False
            self._capture_mem = False
        elif tag == 'div' and self._current_item is not None:
            self.items.append({k: v.strip() for k, v in self._current_item.items()})
            self._current_item = None
        elif tag == 'li' and self._current_li is not None:
            self.li.append(self._current_li)
            self._current_li = None
        if self.stack:
            self.stack.pop()

def parse_memory_gb(text):
    m = re.search(r'(\d+(?:[.,]\d+)?)\s*(GB|MB)\b', text, flags=re.I)
    if not m:
        raise ValueError(f'Cannot parse memory: {text!r}')
    value = float(m.group(1).replace(',', '.'))
    unit = m.group(2).upper()
    if unit == 'MB':
        value /= 1024.0
    return value

def detect_currency(price_text):
    s = price_text.strip()
    if 'NT$' in s:
        return 'NT$'
    if re.search(r'\bUSD\b', s, flags=re.I):
        return 'USD'
    if '€' in s:
        return '€'
    raise ValueError(f'Cannot detect currency: {price_text!r}')

def parse_price(price_text):
    s = price_text.strip()
    currency = detect_currency(s)
    numeric = re.sub(r'(?i)NT\$|USD|€|\s', '', s)
    # European format uses comma as decimal separator; examples: €499.00 and €1.299,00.
    if currency == '€' and ',' in numeric:
        numeric = numeric.replace('.', '').replace(',', '.')
    else:
        numeric = numeric.replace(',', '')
    return float(numeric), currency

def fmt_number(x):
    # keep CSV values clean and numeric-looking without unnecessary trailing zeros
    if abs(x - round(x)) < 1e-12:
        return str(int(round(x)))
    return f'{x:.10f}'.rstrip('0').rstrip('.')

rows = []
for url in URLS:
    with urlopen(url, timeout=10) as resp:
        html = resp.read().decode('utf-8', errors='replace')
    parser = SimpleHTML()
    parser.feed(html)

    if parser.tables:
        table = parser.tables[0]
        header = table[0]
        for data_row in table[1:]:
            record = dict(zip(header, data_row))
            price, currency = parse_price(record['價格'])
            rows.append({
                'Model': record['型號'],
                'Price': price,
                'Currency': currency,
                'MemoryGB': parse_memory_gb(record['記憶體']),
                'SourceURL': url,
            })
    elif parser.items:
        for item in parser.items:
            price, currency = parse_price(item['price'])
            rows.append({
                'Model': item['model'],
                'Price': price,
                'Currency': currency,
                'MemoryGB': parse_memory_gb(item['memory']),
                'SourceURL': url,
            })
    elif parser.li:
        for li in parser.li:
            text = li['text'].strip()
            model = li['attrs'].get('data-model') or text.split('—', 1)[0].strip()
            parts = [p.strip() for p in text.split('—')]
            if len(parts) < 3:
                raise ValueError(f'Cannot parse list item: {text!r}')
            price, currency = parse_price(parts[1])
            rows.append({
                'Model': model,
                'Price': price,
                'Currency': currency,
                'MemoryGB': parse_memory_gb(parts[2]),
                'SourceURL': url,
            })
    else:
        raise ValueError(f'No recognizable product data at {url}')

out_path = OUTPUT_DIR / 'merged_catalog.csv'
fieldnames = ['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL']
with out_path.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({
            'Model': row['Model'],
            'Price': fmt_number(row['Price']),
            'Currency': row['Currency'],
            'MemoryGB': fmt_number(row['MemoryGB']),
            'SourceURL': row['SourceURL'],
        })

# Verification from the saved output file.
with out_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    saved_rows = list(reader)

assert reader.fieldnames == fieldnames, f'Unexpected columns: {reader.fieldnames}'
assert len(saved_rows) == 6, f'Expected 6 rows, got {len(saved_rows)}'
expected = [
    ('NX-1', 12000.0, 'NT$', 16.0, URLS[0]),
    ('NX-2', 8500.0, 'NT$', 8.0, URLS[0]),
    ('NX-1', 399.5, 'USD', 16.0, URLS[1]),
    ('NX-3', 1250.0, 'USD', 32.0, URLS[1]),
    ('NX-4', 499.0, '€', 4.0, URLS[2]),
    ('NX-5', 1299.0, '€', 64.0, URLS[2]),
]
for row, exp in zip(saved_rows, expected):
    assert row['Model'] == exp[0]
    assert abs(float(row['Price']) - exp[1]) < 1e-9
    assert row['Currency'] == exp[2]
    assert abs(float(row['MemoryGB']) - exp[3]) < 1e-9
    assert row['SourceURL'] == exp[4]
# confirm duplicate model is preserved from two sources
assert sum(1 for r in saved_rows if r['Model'] == 'NX-1') == 2

print(f'Wrote {out_path}')
print('Verified columns:', fieldnames)
print('Verified row count:', len(saved_rows))
print('Verified Price numeric parse, Currency retained, MemoryGB conversion, SourceURL, and duplicate NX-1 preservation.')
for r in saved_rows:
    print(r)
