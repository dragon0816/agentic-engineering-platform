from pathlib import Path
from html.parser import HTMLParser
from decimal import Decimal
import urllib.request
import csv
import re

workspace = Path.cwd()
out_dir = workspace / 'output'
out_dir.mkdir(exist_ok=True)
out_file = out_dir / 'catalog_merged.csv'

urls = [
    'http://127.0.0.1:57997/t12/a',
    'http://127.0.0.1:57997/t12/b',
    'http://127.0.0.1:57997/t12/c',
]

class SimpleHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.cells = []
        self.rows = []
        self.current_cell = None
        self.items = []
        self.current_item = None
        self.current_tag = None
        self.lis = []
        self.current_li = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append((tag, attrs))
        self.current_tag = tag
        if tag in ('td', 'th'):
            self.current_cell = ''
        if tag == 'tr':
            self.cells = []
        if tag == 'div' and attrs.get('class') == 'item':
            self.current_item = {'h2': '', 'price': '', 'mem': ''}
        if tag == 'li':
            self.current_li = {'attrs': attrs, 'text': ''}

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.current_cell is not None:
            self.cells.append(self.current_cell.strip())
            self.current_cell = None
        if tag == 'tr' and self.cells:
            self.rows.append(self.cells)
            self.cells = []
        if tag == 'div' and self.current_item is not None:
            if any(v for v in self.current_item.values()):
                self.items.append(self.current_item)
            self.current_item = None
        if tag == 'li' and self.current_li is not None:
            self.current_li['text'] = self.current_li['text'].strip()
            self.lis.append(self.current_li)
            self.current_li = None
        if self.stack:
            self.stack.pop()
        self.current_tag = self.stack[-1][0] if self.stack else None

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell += data
        if self.current_item is not None and self.stack:
            tag, attrs = self.stack[-1]
            if tag == 'h2':
                self.current_item['h2'] += data.strip()
            elif tag == 'p' and attrs.get('class') == 'price':
                self.current_item['price'] += data.strip()
            elif tag == 'p' and attrs.get('class') == 'mem':
                self.current_item['mem'] += data.strip()
        if self.current_li is not None:
            self.current_li['text'] += data

def parse_price(value):
    s = value.strip()
    currency = None
    if s.startswith('NT$'):
        currency = 'NT$'
        num = s[3:].strip()
    elif s.startswith('USD'):
        currency = 'USD'
        num = s[3:].strip()
    elif s.startswith('€'):
        currency = '€'
        num = s[1:].strip()
    else:
        m = re.match(r'([^0-9\-.,]+)\s*(.*)', s)
        if not m:
            raise ValueError(f'Cannot parse currency from {value!r}')
        currency, num = m.group(1), m.group(2)
    # Convert numbers: comma thousands with dot decimal, or European dot thousands with comma decimal.
    num = num.strip()
    if ',' in num and '.' in num:
        if num.rfind(',') > num.rfind('.'):
            normalized = num.replace('.', '').replace(',', '.')
        else:
            normalized = num.replace(',', '')
    elif ',' in num:
        # If only comma and exactly 3 digits after it, treat as thousands; otherwise decimal comma.
        after = num.split(',')[-1]
        if len(after) == 3 and all(part.isdigit() for part in num.split(',')):
            normalized = num.replace(',', '')
        else:
            normalized = num.replace(',', '.')
    else:
        normalized = num
    return currency, Decimal(normalized)

def parse_memory_gb(value):
    s = value.strip()
    m = re.search(r'([0-9]+(?:[.,][0-9]+)?)\s*(GB|MB)', s, re.I)
    if not m:
        raise ValueError(f'Cannot parse memory from {value!r}')
    amount = Decimal(m.group(1).replace(',', '.'))
    unit = m.group(2).upper()
    if unit == 'MB':
        return amount / Decimal(1024)
    return amount

def fmt_decimal(d):
    d = Decimal(d)
    if d == d.to_integral_value():
        return str(d.to_integral_value())
    return format(d.normalize(), 'f')

all_rows = []
for url in urls:
    with urllib.request.urlopen(url, timeout=10) as resp:
        html = resp.read().decode(resp.headers.get_content_charset() or 'utf-8', errors='replace')
    parser = SimpleHTML()
    parser.feed(html)

    if url.endswith('/a'):
        # First row is headers: 型號, 價格, 記憶體.
        for r in parser.rows[1:]:
            model, price_text, mem_text = r[0], r[1], r[2]
            currency, price = parse_price(price_text)
            mem_gb = parse_memory_gb(mem_text)
            all_rows.append({'Model': model, 'Price': fmt_decimal(price), 'Currency': currency, 'MemoryGB': fmt_decimal(mem_gb), 'SourceURL': url})
    elif url.endswith('/b'):
        for item in parser.items:
            model = item['h2']
            currency, price = parse_price(item['price'])
            mem_gb = parse_memory_gb(item['mem'])
            all_rows.append({'Model': model, 'Price': fmt_decimal(price), 'Currency': currency, 'MemoryGB': fmt_decimal(mem_gb), 'SourceURL': url})
    elif url.endswith('/c'):
        for li in parser.lis:
            model = li['attrs'].get('data-model') or li['text'].split('—')[0].strip()
            parts = [p.strip() for p in li['text'].split('—')]
            price_text = parts[1]
            mem_text = parts[2]
            currency, price = parse_price(price_text)
            mem_gb = parse_memory_gb(mem_text)
            all_rows.append({'Model': model, 'Price': fmt_decimal(price), 'Currency': currency, 'MemoryGB': fmt_decimal(mem_gb), 'SourceURL': url})

with out_file.open('w', encoding='utf-8-sig', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL'])
    writer.writeheader()
    writer.writerows(all_rows)

# Reopen and verify every stated requirement.
with out_file.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    read_rows = list(reader)

assert reader.fieldnames == ['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL'], reader.fieldnames
assert len(read_rows) == 6, len(read_rows)
assert [r['Model'] for r in read_rows] == ['NX-1', 'NX-2', 'NX-1', 'NX-3', 'NX-4', 'NX-5']
assert [r['SourceURL'] for r in read_rows] == [urls[0], urls[0], urls[1], urls[1], urls[2], urls[2]]
# Same model from separate sources is retained: two NX-1 rows.
assert sum(1 for r in read_rows if r['Model'] == 'NX-1') == 2
expected = [
    ('12000', 'NT$', '16'),
    ('8500', 'NT$', '8'),
    ('399.5', 'USD', '16'),
    ('1250', 'USD', '32'),
    ('499', '€', '4'),
    ('1299', '€', '64'),
]
for row, (price, currency, mem) in zip(read_rows, expected):
    assert row['Price'] == price, row
    assert row['Currency'] == currency, row
    assert row['MemoryGB'] == mem, row
    Decimal(row['Price'])
    Decimal(row['MemoryGB'])

print('Wrote:', out_file)
print('Rows:', len(read_rows))
print('Columns:', reader.fieldnames)
for r in read_rows:
    print(r)
print('Verification OK: output file reopened; required columns, row count, retained duplicate model by source, numeric Price, currencies, MB-to-GB conversion, and SourceURL values checked.')