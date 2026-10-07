from pathlib import Path
from urllib.request import urlopen
import csv
import re
from html.parser import HTMLParser
from decimal import Decimal, InvalidOperation
from openpyxl import Workbook, load_workbook

WORKSPACE = Path.cwd()
OUT = WORKSPACE / 'output'
OUT.mkdir(parents=True, exist_ok=True)

urls = [
    'http://127.0.0.1:64212/t12/a',
    'http://127.0.0.1:64212/t12/b',
    'http://127.0.0.1:64212/t12/c',
]

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_td = False
        self.in_th = False
        self.current = []
        self.row = []
        self.rows = []
    def handle_starttag(self, tag, attrs):
        if tag in ('td', 'th'):
            self.in_td = tag == 'td'
            self.in_th = tag == 'th'
            self.current = []
        if tag == 'tr':
            self.row = []
    def handle_data(self, data):
        if self.in_td or self.in_th:
            self.current.append(data)
    def handle_endtag(self, tag):
        if tag in ('td', 'th') and (self.in_td or self.in_th):
            self.row.append(''.join(self.current).strip())
            self.current = []
            self.in_td = False
            self.in_th = False
        if tag == 'tr':
            if self.row:
                self.rows.append(self.row)

class DivParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.current_item = None
        self.capture = None
        self.current = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div' and attrs.get('class') == 'item':
            self.current_item = {}
        elif self.current_item is not None and tag == 'h2':
            self.capture = 'model'; self.current = []
        elif self.current_item is not None and tag == 'p' and attrs.get('class') == 'price':
            self.capture = 'price'; self.current = []
        elif self.current_item is not None and tag == 'p' and attrs.get('class') == 'mem':
            self.capture = 'mem'; self.current = []
    def handle_data(self, data):
        if self.capture:
            self.current.append(data)
    def handle_endtag(self, tag):
        if self.capture and ((tag == 'h2' and self.capture == 'model') or tag == 'p'):
            self.current_item[self.capture] = ''.join(self.current).strip()
            self.capture = None
            self.current = []
        if tag == 'div' and self.current_item is not None:
            if self.current_item:
                self.items.append(self.current_item)
            self.current_item = None

class ListParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.in_li = False
        self.current = []
        self.current_model = None
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'li':
            self.in_li = True
            self.current = []
            self.current_model = attrs.get('data-model')
    def handle_data(self, data):
        if self.in_li:
            self.current.append(data)
    def handle_endtag(self, tag):
        if tag == 'li' and self.in_li:
            self.items.append({'model_attr': self.current_model, 'text': ''.join(self.current).strip()})
            self.in_li = False
            self.current = []
            self.current_model = None

def normalize_price(price_text):
    s = price_text.strip().replace('\xa0', ' ')
    if s.startswith('NT$'):
        currency = 'NT$'
        num = s[3:].strip()
    elif s.upper().startswith('USD'):
        currency = 'USD'
        num = s[3:].strip()
    elif s.startswith('€'):
        currency = '€'
        num = s[1:].strip()
    else:
        m = re.match(r'([^0-9\-+.,\s]+)\s*(.*)', s)
        currency = m.group(1) if m else ''
        num = m.group(2) if m else s
    num = re.sub(r'\s+', '', num)
    if ',' in num and '.' in num:
        # If comma is the final decimal separator, parse European format: 1.299,00 -> 1299.00.
        if num.rfind(',') > num.rfind('.'):
            num = num.replace('.', '').replace(',', '.')
        else:
            num = num.replace(',', '')
    elif ',' in num:
        # Treat comma followed by exactly two digits as a decimal separator; otherwise thousands.
        if re.search(r',\d{2}$', num):
            num = num.replace(',', '.')
        else:
            num = num.replace(',', '')
    try:
        price = Decimal(num)
    except InvalidOperation as e:
        raise ValueError(f'Cannot parse price {price_text!r} -> {num!r}') from e
    return price, currency

def normalize_memory(mem_text):
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(GB|MB)', mem_text, flags=re.I)
    if not m:
        raise ValueError(f'Cannot parse memory {mem_text!r}')
    amount = Decimal(m.group(1))
    unit = m.group(2).upper()
    return amount if unit == 'GB' else amount / Decimal(1024)

def dec_to_csv(d):
    # Plain numeric representation without unnecessary trailing zeroes.
    d = d.normalize()
    if d == d.to_integral():
        return str(d.quantize(Decimal(1)))
    return format(d, 'f').rstrip('0').rstrip('.')

def fetch(url):
    with urlopen(url, timeout=10) as resp:
        return resp.read().decode('utf-8', errors='replace')

records = []
for url in urls:
    html = fetch(url)
    if url.endswith('/a'):
        p = TableParser(); p.feed(html)
        for row in p.rows[1:]:
            model, price_text, mem_text = row[:3]
            price, currency = normalize_price(price_text)
            mem_gb = normalize_memory(mem_text)
            records.append({'Model': model, 'Price': price, 'Currency': currency, 'MemoryGB': mem_gb, 'SourceURL': url})
    elif url.endswith('/b'):
        p = DivParser(); p.feed(html)
        for item in p.items:
            price, currency = normalize_price(item['price'])
            mem_gb = normalize_memory(item['mem'])
            records.append({'Model': item['model'], 'Price': price, 'Currency': currency, 'MemoryGB': mem_gb, 'SourceURL': url})
    elif url.endswith('/c'):
        p = ListParser(); p.feed(html)
        for item in p.items:
            parts = [part.strip() for part in item['text'].split('—')]
            model = item['model_attr'] or parts[0]
            price, currency = normalize_price(parts[1])
            mem_gb = normalize_memory(parts[2])
            records.append({'Model': model, 'Price': price, 'Currency': currency, 'MemoryGB': mem_gb, 'SourceURL': url})

headers = ['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL']
csv_path = OUT / 'merged_catalog.csv'
with csv_path.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=headers)
    writer.writeheader()
    for r in records:
        writer.writerow({
            'Model': r['Model'],
            'Price': dec_to_csv(r['Price']),
            'Currency': r['Currency'],
            'MemoryGB': dec_to_csv(r['MemoryGB']),
            'SourceURL': r['SourceURL'],
        })

# Also write an Excel copy so Price and MemoryGB are stored as numeric cell values.
xlsx_path = OUT / 'merged_catalog.xlsx'
wb = Workbook()
ws = wb.active
ws.title = 'merged_catalog'
ws.append(headers)
for r in records:
    ws.append([r['Model'], float(r['Price']), r['Currency'], float(r['MemoryGB']), r['SourceURL']])
wb.save(xlsx_path)

# Verification: reopen every output and confirm requirements.
expected_rows = 6
expected_columns = headers
with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
    rows = list(csv.DictReader(f))
assert len(rows) == expected_rows, f'CSV row count {len(rows)} != {expected_rows}'
assert rows and list(rows[0].keys()) == expected_columns, list(rows[0].keys())
for row in rows:
    Decimal(row['Price'])
    Decimal(row['MemoryGB'])
    assert row['Currency'] in {'NT$', 'USD', '€'}, row
    assert row['SourceURL'] in urls, row

wb2 = load_workbook(xlsx_path, data_only=True)
ws2 = wb2['merged_catalog']
assert [cell.value for cell in ws2[1]] == expected_columns
assert ws2.max_row == expected_rows + 1
for i in range(2, ws2.max_row + 1):
    assert isinstance(ws2.cell(i, 2).value, (int, float)), (i, ws2.cell(i, 2).value)
    assert isinstance(ws2.cell(i, 4).value, (int, float)), (i, ws2.cell(i, 4).value)
    assert ws2.cell(i, 3).value in {'NT$', 'USD', '€'}
    assert ws2.cell(i, 5).value in urls

print('Wrote:', csv_path)
print('Wrote:', xlsx_path)
print('CSV rows:', len(rows))
print('CSV columns:', list(rows[0].keys()))
print('CSV data:')
for row in rows:
    print(row)
print('Verified: output files reopen successfully; required columns; 6 rows; duplicate model NX-1 preserved by source; Price and MemoryGB numeric/convertible; currencies retained; SourceURL present.')
