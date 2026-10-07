import csv
import re
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URLS = [
    'http://127.0.0.1:50351/t12/a',
    'http://127.0.0.1:50351/t12/b',
    'http://127.0.0.1:50351/t12/c',
]
OUT = Path('output') / 'merged_catalog.csv'

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_cell = False
        self.cell_parts = []
        self.current_row = []
        self.rows = []
        self.in_row = False
    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self.in_row = True
            self.current_row = []
        elif tag in ('td', 'th') and self.in_row:
            self.in_cell = True
            self.cell_parts = []
    def handle_data(self, data):
        if self.in_cell:
            self.cell_parts.append(data)
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.in_cell:
            self.current_row.append(' '.join(''.join(self.cell_parts).split()))
            self.in_cell = False
        elif tag == 'tr' and self.in_row:
            self.rows.append(self.current_row)
            self.in_row = False

class DivItemParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.depth = 0
        self.current = None
        self.capture = None
        self.parts = []
        self.items = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div' and attrs.get('class') == 'item':
            self.current = {}
            self.depth = 1
            return
        if self.current is not None:
            self.depth += 1
            if tag == 'h2':
                self.capture = 'model'; self.parts = []
            elif tag == 'p' and attrs.get('class') == 'price':
                self.capture = 'price'; self.parts = []
            elif tag == 'p' and attrs.get('class') == 'mem':
                self.capture = 'memory'; self.parts = []
    def handle_data(self, data):
        if self.capture:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if self.capture and ((self.capture == 'model' and tag == 'h2') or (self.capture in ('price','memory') and tag == 'p')):
            self.current[self.capture] = ' '.join(''.join(self.parts).split())
            self.capture = None
        if self.current is not None:
            self.depth -= 1
            if tag == 'div' and self.depth <= 0:
                self.items.append(self.current)
                self.current = None

class LiParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_li = False
        self.model = None
        self.parts = []
        self.items = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'li':
            self.in_li = True
            self.model = attrs.get('data-model')
            self.parts = []
    def handle_data(self, data):
        if self.in_li:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == 'li' and self.in_li:
            text = ' '.join(''.join(self.parts).split())
            self.items.append({'model': self.model, 'text': text})
            self.in_li = False

def fetch(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.read().decode('utf-8', errors='replace')

def parse_memory_gb(text):
    m = re.search(r'([0-9]+(?:[.,][0-9]+)?)\s*(GB|MB)\b', text, re.I)
    if not m:
        raise ValueError(f'Cannot parse memory: {text!r}')
    val = float(m.group(1).replace(',', '.'))
    unit = m.group(2).upper()
    gb = val if unit == 'GB' else val / 1024.0
    return gb

def parse_price(text):
    s = text.strip()
    if s.startswith('NT$'):
        currency = 'NT$'
        num = s[3:].strip().replace(',', '')
    elif s.upper().startswith('USD'):
        currency = 'USD'
        num = s[3:].strip().replace(',', '')
    elif s.startswith('€'):
        currency = '€'
        num = s[1:].strip()
        # European style in source c: dot thousands separator, comma decimal separator.
        if ',' in num:
            num = num.replace('.', '').replace(',', '.')
        else:
            num = num.replace(',', '')
    else:
        m = re.match(r'([^0-9\s]+|[A-Z]{3})\s*(.+)', s)
        if not m:
            raise ValueError(f'Cannot parse price: {text!r}')
        currency = m.group(1)
        num = m.group(2).replace(',', '')
    return float(num), currency

def fmt_num(x):
    # Keep CSV compact while preserving numeric interpretation.
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return ('%.10f' % x).rstrip('0').rstrip('.')

records = []
for url in URLS:
    html = fetch(url)
    if url.endswith('/a'):
        p = TableParser(); p.feed(html)
        for row in p.rows[1:]:
            if len(row) >= 3:
                price, currency = parse_price(row[1])
                records.append({
                    'Model': row[0],
                    'Price': price,
                    'Currency': currency,
                    'MemoryGB': parse_memory_gb(row[2]),
                    'SourceURL': url,
                })
    elif url.endswith('/b'):
        p = DivItemParser(); p.feed(html)
        for item in p.items:
            price, currency = parse_price(item['price'])
            records.append({
                'Model': item['model'],
                'Price': price,
                'Currency': currency,
                'MemoryGB': parse_memory_gb(item['memory']),
                'SourceURL': url,
            })
    elif url.endswith('/c'):
        p = LiParser(); p.feed(html)
        for item in p.items:
            parts = [x.strip() for x in item['text'].split('—')]
            model = item['model'] or parts[0]
            price_text = parts[1]
            mem_text = parts[2]
            price, currency = parse_price(price_text)
            records.append({
                'Model': model,
                'Price': price,
                'Currency': currency,
                'MemoryGB': parse_memory_gb(mem_text),
                'SourceURL': url,
            })

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=['Model','Price','Currency','MemoryGB','SourceURL'])
    writer.writeheader()
    for r in records:
        writer.writerow({
            'Model': r['Model'],
            'Price': fmt_num(r['Price']),
            'Currency': r['Currency'],
            'MemoryGB': fmt_num(r['MemoryGB']),
            'SourceURL': r['SourceURL'],
        })

# Verification by reopening output file.
with OUT.open('r', newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
print('wrote', OUT)
print('headers', rows[0].keys() if rows else [])
print('row_count', len(rows))
for row in rows:
    float(row['Price'])
    float(row['MemoryGB'])
    assert row['SourceURL'] in URLS
    assert set(row.keys()) == {'Model','Price','Currency','MemoryGB','SourceURL'}
print('rows:')
for row in rows:
    print(row)
assert [r['Model'] for r in rows] == ['NX-1','NX-2','NX-1','NX-3','NX-4','NX-5']
assert rows[0]['Price'] == '12000' and rows[0]['Currency'] == 'NT$' and rows[0]['MemoryGB'] == '16'
assert rows[1]['Price'] == '8500' and rows[1]['MemoryGB'] == '8'
assert rows[2]['Price'] == '399.5' and rows[2]['Currency'] == 'USD' and rows[2]['MemoryGB'] == '16'
assert rows[3]['Price'] == '1250' and rows[3]['MemoryGB'] == '32'
assert rows[4]['Price'] == '499' and rows[4]['Currency'] == '€' and rows[4]['MemoryGB'] == '4'
assert rows[5]['Price'] == '1299' and rows[5]['MemoryGB'] == '64'
print('verification OK: exact headers/order, 6 rows, numeric Price/MemoryGB, source URLs retained, duplicates by source retained')