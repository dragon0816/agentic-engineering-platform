from pathlib import Path
from urllib.request import urlopen
from html.parser import HTMLParser
import csv
import re

WORKSPACE = Path.cwd()
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
URLS = [
    'http://127.0.0.1:50447/t12/a',
    'http://127.0.0.1:50447/t12/b',
    'http://127.0.0.1:50447/t12/c',
]

class SimpleHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.tables = []
        self.current_table = None
        self.current_row = None
        self.current_cell = None
        self.items = []
        self.current_item = None
        self.current_tag_text = None
        self.lis = []
        self.current_li = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append((tag, attrs))
        if tag == 'table' and attrs.get('id') == 'p':
            self.current_table = []
        elif tag == 'tr' and self.current_table is not None:
            self.current_row = []
        elif tag in ('td', 'th') and self.current_row is not None:
            self.current_cell = ''
        elif tag == 'div' and attrs.get('class') == 'item':
            self.current_item = {'texts': {}}
        elif self.current_item is not None and tag in ('h2', 'p'):
            self.current_tag_text = {'tag': tag, 'class': attrs.get('class',''), 'text': ''}
        elif tag == 'li':
            self.current_li = {'attrs': attrs, 'text': ''}

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell += data
        if self.current_tag_text is not None:
            self.current_tag_text['text'] += data
        if self.current_li is not None:
            self.current_li['text'] += data

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.current_cell is not None:
            self.current_row.append(self.current_cell.strip())
            self.current_cell = None
        elif tag == 'tr' and self.current_row is not None:
            self.current_table.append(self.current_row)
            self.current_row = None
        elif tag == 'table' and self.current_table is not None:
            self.tables.append(self.current_table)
            self.current_table = None
        elif self.current_tag_text is not None and tag == self.current_tag_text['tag']:
            key = self.current_tag_text['class'] or self.current_tag_text['tag']
            self.current_item['texts'][key] = self.current_tag_text['text'].strip()
            self.current_tag_text = None
        elif tag == 'div' and self.current_item is not None:
            self.items.append(self.current_item)
            self.current_item = None
        elif tag == 'li' and self.current_li is not None:
            self.lis.append(self.current_li)
            self.current_li = None
        if self.stack:
            self.stack.pop()

def price_currency(raw):
    raw = raw.strip()
    if raw.startswith('NT$'):
        currency = 'NTD'
        num = raw.replace('NT$', '').replace(',', '')
    elif raw.startswith('USD'):
        currency = 'USD'
        num = raw.replace('USD', '').strip().replace(',', '')
    elif raw.startswith('€'):
        currency = 'EUR'
        num = raw.replace('€', '').strip()
        # European thousands/decimal format if both separators appear with comma last.
        if '.' in num and ',' in num and num.rfind(',') > num.rfind('.'):
            num = num.replace('.', '').replace(',', '.')
        else:
            num = num.replace(',', '')
    else:
        raise ValueError(f'Unknown currency in price: {raw!r}')
    return float(num), currency

def memory_gb(raw):
    raw = raw.strip()
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(GB|MB)', raw, flags=re.I)
    if not m:
        raise ValueError(f'No memory value found: {raw!r}')
    val = float(m.group(1))
    unit = m.group(2).upper()
    gb = val if unit == 'GB' else val / 1024.0
    return gb

def fmt_number(x):
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return ('%.10f' % x).rstrip('0').rstrip('.')

rows = []
for url in URLS:
    body = urlopen(url, timeout=10).read().decode('utf-8')
    parser = SimpleHTML()
    parser.feed(body)
    print(f'Parsed {url}: tables={len(parser.tables)}, items={len(parser.items)}, lis={len(parser.lis)}')

    if url.endswith('/a'):
        table = parser.tables[0]
        headers = table[0]
        print('A headers:', headers)
        for r in table[1:]:
            rec = dict(zip(headers, r))
            price, currency = price_currency(rec['價格'])
            rows.append({
                'Model': rec['型號'],
                'Price': price,
                'Currency': currency,
                'MemoryGB': memory_gb(rec['記憶體']),
                'SourceURL': url,
            })
    elif url.endswith('/b'):
        for item in parser.items:
            txt = item['texts']
            price, currency = price_currency(txt['price'])
            rows.append({
                'Model': txt['h2'],
                'Price': price,
                'Currency': currency,
                'MemoryGB': memory_gb(txt['mem']),
                'SourceURL': url,
            })
    elif url.endswith('/c'):
        for li in parser.lis:
            text = li['text'].strip()
            parts = [p.strip() for p in text.split('—')]
            model = li['attrs'].get('data-model') or parts[0]
            price, currency = price_currency(parts[1])
            rows.append({
                'Model': model,
                'Price': price,
                'Currency': currency,
                'MemoryGB': memory_gb(parts[2]),
                'SourceURL': url,
            })

out_path = OUTPUT / 'merged_products.csv'
with out_path.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL'])
    writer.writeheader()
    for row in rows:
        writer.writerow({
            'Model': row['Model'],
            'Price': fmt_number(row['Price']),
            'Currency': row['Currency'],
            'MemoryGB': fmt_number(row['MemoryGB']),
            'SourceURL': row['SourceURL'],
        })

# Verification: reopen output and check stated requirements.
with out_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    read_rows = list(reader)

expected_fields = ['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL']
assert reader.fieldnames == expected_fields, reader.fieldnames
assert len(read_rows) == 6, len(read_rows)
assert [r['Model'] for r in read_rows] == ['NX-1','NX-2','NX-1','NX-3','NX-4','NX-5']
assert [r['SourceURL'] for r in read_rows] == [URLS[0], URLS[0], URLS[1], URLS[1], URLS[2], URLS[2]]
for r in read_rows:
    float(r['Price'])
    float(r['MemoryGB'])
    assert r['Currency'] in {'NTD','USD','EUR'}

expected = [
    ('NX-1', 12000.0, 'NTD', 16.0, URLS[0]),
    ('NX-2', 8500.0, 'NTD', 8.0, URLS[0]),
    ('NX-1', 399.50, 'USD', 16.0, URLS[1]),
    ('NX-3', 1250.0, 'USD', 32.0, URLS[1]),
    ('NX-4', 499.0, 'EUR', 4.0, URLS[2]),
    ('NX-5', 1299.0, 'EUR', 64.0, URLS[2]),
]
for got, exp in zip(read_rows, expected):
    assert got['Model'] == exp[0]
    assert abs(float(got['Price']) - exp[1]) < 1e-9, (got, exp)
    assert got['Currency'] == exp[2]
    assert abs(float(got['MemoryGB']) - exp[3]) < 1e-9, (got, exp)
    assert got['SourceURL'] == exp[4]

print('Wrote:', out_path)
print('Rows:', len(read_rows))
print('Columns:', reader.fieldnames)
print('Verified numeric Price, numeric MemoryGB, currencies retained, duplicate model rows preserved by source URL.')
for r in read_rows:
    print(r)
