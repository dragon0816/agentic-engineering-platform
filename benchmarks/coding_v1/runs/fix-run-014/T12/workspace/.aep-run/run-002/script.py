from pathlib import Path
from urllib.request import urlopen
from html.parser import HTMLParser
import csv
import re
from decimal import Decimal

workspace = Path.cwd()
out_dir = workspace / 'output'
out_dir.mkdir(parents=True, exist_ok=True)
out_path = out_dir / 'catalog_products.csv'

urls = [
    'http://127.0.0.1:63668/t12/a',
    'http://127.0.0.1:63668/t12/b',
    'http://127.0.0.1:63668/t12/c',
]

class CatalogParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.table_rows = []
        self.current_tr = None
        self.current_cell = None
        self.items = []
        self.current_div = None
        self.current_h2 = False
        self.current_p_class = None
        self.lis = []
        self.current_li = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.stack.append((tag, attrs))
        if tag == 'tr':
            self.current_tr = []
        elif tag in ('td', 'th') and self.current_tr is not None:
            self.current_cell = ''
        elif tag == 'div' and attrs.get('class') == 'item':
            self.current_div = {'model':'', 'price':'', 'mem':''}
        elif tag == 'h2' and self.current_div is not None:
            self.current_h2 = True
        elif tag == 'p' and self.current_div is not None:
            self.current_p_class = attrs.get('class')
        elif tag == 'li':
            self.current_li = {'attrs': attrs, 'text': ''}

    def handle_data(self, data):
        if self.current_cell is not None:
            self.current_cell += data
        if self.current_div is not None:
            if self.current_h2:
                self.current_div['model'] += data
            elif self.current_p_class == 'price':
                self.current_div['price'] += data
            elif self.current_p_class == 'mem':
                self.current_div['mem'] += data
        if self.current_li is not None:
            self.current_li['text'] += data

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.current_tr is not None and self.current_cell is not None:
            self.current_tr.append(self.current_cell.strip())
            self.current_cell = None
        elif tag == 'tr' and self.current_tr is not None:
            self.table_rows.append(self.current_tr)
            self.current_tr = None
        elif tag == 'h2':
            self.current_h2 = False
        elif tag == 'p':
            self.current_p_class = None
        elif tag == 'div' and self.current_div is not None:
            self.items.append({k:v.strip() for k,v in self.current_div.items()})
            self.current_div = None
        elif tag == 'li' and self.current_li is not None:
            self.lis.append({'attrs': self.current_li['attrs'], 'text': self.current_li['text'].strip()})
            self.current_li = None
        if self.stack:
            self.stack.pop()

def currency_and_price(raw):
    s = raw.strip()
    if 'NT$' in s:
        cur = 'NTD'
    elif 'USD' in s:
        cur = 'USD'
    elif '€' in s:
        cur = 'EUR'
    else:
        cur = ''
    cleaned = re.sub(r'(NT\$|USD|€|\s)', '', s)
    # If both separators exist, the rightmost separator is the decimal separator.
    if ',' in cleaned and '.' in cleaned:
        if cleaned.rfind(',') > cleaned.rfind('.'):
            cleaned = cleaned.replace('.', '').replace(',', '.')
        else:
            cleaned = cleaned.replace(',', '')
    elif ',' in cleaned:
        parts = cleaned.split(',')
        if len(parts[-1]) == 2 and any(len(p) != 3 for p in parts[1:-1]):
            cleaned = ''.join(parts[:-1]).replace(',', '') + '.' + parts[-1]
        elif len(parts[-1]) == 2 and len(parts) == 2 and len(parts[0]) <= 3:
            cleaned = parts[0] + '.' + parts[-1]
        else:
            cleaned = cleaned.replace(',', '')
    price = Decimal(cleaned)
    return cur, price

def memory_gb(raw):
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(GB|MB)', raw, flags=re.I)
    if not m:
        raise ValueError(f'Cannot parse memory: {raw}')
    value = Decimal(m.group(1))
    unit = m.group(2).upper()
    if unit == 'MB':
        value = value / Decimal(1024)
    return value

def dec_to_text(d):
    d = d.normalize()
    # Avoid scientific notation for whole/normal decimal values.
    return format(d, 'f')

records = []
for url in urls:
    with urlopen(url, timeout=10) as r:
        html = r.read().decode('utf-8', errors='replace')
    parser = CatalogParser()
    parser.feed(html)

    # URL A: table with header 型號, 價格, 記憶體
    if parser.table_rows:
        header = parser.table_rows[0]
        for row in parser.table_rows[1:]:
            data = dict(zip(header, row))
            cur, price = currency_and_price(data['價格'])
            mem = memory_gb(data['記憶體'])
            records.append({
                'Model': data['型號'],
                'Price': dec_to_text(price),
                'Currency': cur,
                'MemoryGB': dec_to_text(mem),
                'SourceURL': url,
            })

    # URL B: div.item blocks
    for item in parser.items:
        cur, price = currency_and_price(item['price'])
        mem = memory_gb(item['mem'])
        records.append({
            'Model': item['model'],
            'Price': dec_to_text(price),
            'Currency': cur,
            'MemoryGB': dec_to_text(mem),
            'SourceURL': url,
        })

    # URL C: list items: MODEL — PRICE — MEMORY
    for li in parser.lis:
        text = li['text']
        parts = [p.strip() for p in text.split('—')]
        model = li['attrs'].get('data-model') or parts[0]
        price_raw = parts[1]
        mem_raw = parts[2]
        cur, price = currency_and_price(price_raw)
        mem = memory_gb(mem_raw)
        records.append({
            'Model': model,
            'Price': dec_to_text(price),
            'Currency': cur,
            'MemoryGB': dec_to_text(mem),
            'SourceURL': url,
        })

with out_path.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=['Model','Price','Currency','MemoryGB','SourceURL'])
    writer.writeheader()
    writer.writerows(records)

# Reopen and validate every stated requirement.
with out_path.open('r', newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))

assert out_path.exists(), 'output file missing'
assert rows, 'no rows written'
assert list(rows[0].keys()) == ['Model','Price','Currency','MemoryGB','SourceURL'], 'wrong columns'
assert len(rows) == 6, f'expected 6 product rows, got {len(rows)}'
assert sum(1 for r in rows if r['Model'] == 'NX-1') == 2, 'same model from different sources was not preserved'
for r in rows:
    Decimal(r['Price'])
    Decimal(r['MemoryGB'])
    assert r['Currency'] in {'NTD','USD','EUR'}, f"bad currency {r['Currency']}"
    assert r['SourceURL'] in urls, f"bad source {r['SourceURL']}"

expected = [
    {'Model':'NX-1','Price':'12000','Currency':'NTD','MemoryGB':'16','SourceURL':urls[0]},
    {'Model':'NX-2','Price':'8500','Currency':'NTD','MemoryGB':'8','SourceURL':urls[0]},
    {'Model':'NX-1','Price':'399.5','Currency':'USD','MemoryGB':'16','SourceURL':urls[1]},
    {'Model':'NX-3','Price':'1250','Currency':'USD','MemoryGB':'32','SourceURL':urls[1]},
    {'Model':'NX-4','Price':'499','Currency':'EUR','MemoryGB':'4','SourceURL':urls[2]},
    {'Model':'NX-5','Price':'1299','Currency':'EUR','MemoryGB':'64','SourceURL':urls[2]},
]
assert rows == expected, f'rows differ from expected: {rows}'

print('wrote:', out_path)
print('row_count:', len(rows))
print('columns:', list(rows[0].keys()))
print('validated numeric Price and MemoryGB, currencies preserved, duplicate NX-1 preserved, SourceURL set')
for r in rows:
    print(r)
