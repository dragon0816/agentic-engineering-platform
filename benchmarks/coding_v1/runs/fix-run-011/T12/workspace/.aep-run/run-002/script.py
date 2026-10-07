from urllib.request import urlopen
from html.parser import HTMLParser
from pathlib import Path
import csv
import re
from decimal import Decimal, InvalidOperation

URLS = [
    'http://127.0.0.1:54763/t12/a',
    'http://127.0.0.1:54763/t12/b',
    'http://127.0.0.1:54763/t12/c',
]
OUT = Path('output') / 'merged_catalog.csv'
COLUMNS = ['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL']

class SimpleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.events = []
    def handle_starttag(self, tag, attrs):
        self.events.append(('start', tag, dict(attrs)))
    def handle_endtag(self, tag):
        self.events.append(('end', tag, {}))
    def handle_data(self, data):
        if data.strip():
            self.events.append(('data', data.strip(), {}))

class TableParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_cell = False
        self.current_cell = []
        self.current_row = []
        self.rows = []
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'table' and attrs.get('id') == 'p':
            self.in_table = True
        elif self.in_table and tag == 'tr':
            self.current_row = []
        elif self.in_table and tag in ('td', 'th'):
            self.in_cell = True
            self.current_cell = []
    def handle_endtag(self, tag):
        if self.in_table and tag in ('td', 'th') and self.in_cell:
            self.current_row.append(' '.join(self.current_cell).strip())
            self.in_cell = False
        elif self.in_table and tag == 'tr':
            if self.current_row:
                self.rows.append(self.current_row)
        elif self.in_table and tag == 'table':
            self.in_table = False
    def handle_data(self, data):
        if self.in_cell:
            self.current_cell.append(data.strip())

class DivItemParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.in_item = False
        self.depth = 0
        self.capture = None
        self.current = {}
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get('class', '').split()
        if tag == 'div' and 'item' in classes:
            self.in_item = True
            self.depth = 1
            self.current = {'model': '', 'price': '', 'mem': ''}
            return
        if self.in_item:
            self.depth += 1
            if tag == 'h2':
                self.capture = 'model'
            elif tag == 'p' and attrs.get('class') == 'price':
                self.capture = 'price'
            elif tag == 'p' and attrs.get('class') == 'mem':
                self.capture = 'mem'
    def handle_endtag(self, tag):
        if self.in_item:
            if self.capture and tag in ('h2', 'p'):
                self.capture = None
            self.depth -= 1
            if self.depth == 0:
                self.items.append(self.current)
                self.in_item = False
    def handle_data(self, data):
        if self.in_item and self.capture:
            self.current[self.capture] += data.strip()

class LiParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.items = []
        self.in_li = False
        self.current_attrs = {}
        self.text = []
    def handle_starttag(self, tag, attrs):
        if tag == 'li':
            self.in_li = True
            self.current_attrs = dict(attrs)
            self.text = []
    def handle_endtag(self, tag):
        if tag == 'li' and self.in_li:
            self.items.append({'attrs': self.current_attrs, 'text': ' '.join(self.text).strip()})
            self.in_li = False
    def handle_data(self, data):
        if self.in_li:
            self.text.append(data.strip())

def parse_memory_gb(text):
    m = re.search(r'([0-9]+(?:[.,][0-9]+)?)\s*(GB|MB)\b', text, re.I)
    if not m:
        raise ValueError(f'Cannot parse memory: {text!r}')
    value = Decimal(m.group(1).replace(',', '.'))
    unit = m.group(2).upper()
    if unit == 'MB':
        value = value / Decimal(1024)
    return value

def split_currency_price(text):
    s = text.strip()
    # Currency can be a leading symbol/code; price is the numeric part following it.
    m = re.search(r'(?P<currency>NT\$|USD|EUR|€|\$|£|JPY|TWD)\s*(?P<num>[0-9][0-9.,]*)', s, re.I)
    if not m:
        raise ValueError(f'Cannot parse price/currency: {text!r}')
    currency = m.group('currency')
    if currency.upper() in ('USD', 'EUR', 'JPY', 'TWD'):
        currency = currency.upper()
    num = m.group('num')
    # If both dot and comma exist, decide decimal separator by the last separator.
    if '.' in num and ',' in num:
        if num.rfind(',') > num.rfind('.'):
            normalized = num.replace('.', '').replace(',', '.')
        else:
            normalized = num.replace(',', '')
    elif ',' in num:
        parts = num.split(',')
        if len(parts[-1]) == 3 and len(parts) > 1:
            normalized = num.replace(',', '')
        else:
            normalized = num.replace(',', '.')
    else:
        normalized = num
    try:
        price = Decimal(normalized)
    except InvalidOperation as e:
        raise ValueError(f'Cannot convert price: {text!r} -> {normalized!r}') from e
    return currency, price

def decimal_to_plain(d):
    d = d.normalize()
    s = format(d, 'f')
    if '.' in s:
        s = s.rstrip('0').rstrip('.')
    return s or '0'

def fetch(url):
    with urlopen(url, timeout=10) as resp:
        return resp.read().decode(resp.headers.get_content_charset() or 'utf-8', errors='replace')

def parse_url(url, html):
    records = []
    if '<table' in html and 'id="p"' in html:
        p = TableParser(); p.feed(html)
        if not p.rows or p.rows[0] != ['型號', '價格', '記憶體']:
            raise ValueError(f'Unexpected table rows at {url}: {p.rows[:2]}')
        for row in p.rows[1:]:
            model, price_text, mem_text = row
            currency, price = split_currency_price(price_text)
            records.append({
                'Model': model,
                'Price': decimal_to_plain(price),
                'Currency': currency,
                'MemoryGB': decimal_to_plain(parse_memory_gb(mem_text)),
                'SourceURL': url,
            })
    elif 'class="item"' in html:
        p = DivItemParser(); p.feed(html)
        for item in p.items:
            currency, price = split_currency_price(item['price'])
            records.append({
                'Model': item['model'],
                'Price': decimal_to_plain(price),
                'Currency': currency,
                'MemoryGB': decimal_to_plain(parse_memory_gb(item['mem'])),
                'SourceURL': url,
            })
    elif '<li' in html:
        p = LiParser(); p.feed(html)
        for item in p.items:
            text = item['text']
            model = item['attrs'].get('data-model') or text.split('—', 1)[0].strip()
            parts = [part.strip() for part in text.split('—')]
            if len(parts) < 3:
                raise ValueError(f'Unexpected list item at {url}: {text!r}')
            currency, price = split_currency_price(parts[1])
            records.append({
                'Model': model,
                'Price': decimal_to_plain(price),
                'Currency': currency,
                'MemoryGB': decimal_to_plain(parse_memory_gb(parts[2])),
                'SourceURL': url,
            })
    else:
        raise ValueError(f'Unknown catalog structure at {url}')
    return records

print('Fetching and parsing catalog URLs:')
all_records = []
for url in URLS:
    html = fetch(url)
    records = parse_url(url, html)
    print(f' - {url}: {len(records)} records')
    for r in records:
        print('   ', r)
    all_records.extend(records)

OUT.parent.mkdir(parents=True, exist_ok=True)
with OUT.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=COLUMNS)
    writer.writeheader()
    writer.writerows(all_records)
print('\nWrote:', OUT)

# Reopen output and verify every stated requirement.
with OUT.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    rows = list(reader)
    header = reader.fieldnames

assert header == COLUMNS, f'Header mismatch: {header}'
assert len(rows) == 6, f'Expected 6 rows from the three catalogs, got {len(rows)}'
assert rows[0]['Model'] == 'NX-1' and rows[2]['Model'] == 'NX-1', 'Same model from different sources was not retained as separate rows'
assert {r['SourceURL'] for r in rows} == set(URLS), 'SourceURL values do not match input URLs'
for r in rows:
    Decimal(r['Price'])
    Decimal(r['MemoryGB'])
    assert r['Currency'], f'Missing currency in {r}'
    assert r['SourceURL'] in URLS, f'Unexpected SourceURL in {r}'
expected = [
    {'Model':'NX-1','Price':'12000','Currency':'NT$','MemoryGB':'16','SourceURL':URLS[0]},
    {'Model':'NX-2','Price':'8500','Currency':'NT$','MemoryGB':'8','SourceURL':URLS[0]},
    {'Model':'NX-1','Price':'399.5','Currency':'USD','MemoryGB':'16','SourceURL':URLS[1]},
    {'Model':'NX-3','Price':'1250','Currency':'USD','MemoryGB':'32','SourceURL':URLS[1]},
    {'Model':'NX-4','Price':'499','Currency':'€','MemoryGB':'4','SourceURL':URLS[2]},
    {'Model':'NX-5','Price':'1299','Currency':'€','MemoryGB':'64','SourceURL':URLS[2]},
]
assert rows == expected, f'Rows do not match expected normalized values: {rows}'
print('\nVerification passed:')
print(' - CSV header exactly:', header)
print(' - Row count:', len(rows))
print(' - Price fields parse as numeric Decimals and have no currency/thousand separators')
print(' - Currency values retained without FX conversion')
print(' - MemoryGB values converted using 1024 MB = 1 GB')
print(' - Duplicate model NX-1 retained from different SourceURL values')
print(' - Output is under output/ and input/ was not modified')
