import csv
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import urlopen
from openpyxl import Workbook

URLS = [
    'http://127.0.0.1:51979/t12/a',
    'http://127.0.0.1:51979/t12/b',
    'http://127.0.0.1:51979/t12/c',
]
OUT = Path('output')
OUT.mkdir(parents=True, exist_ok=True)

class SimpleHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.current_row = None
        self.in_cell = False
        self.cell_text = ''
        self.items = []
        self.current_item = None
        self.capture_tag = None
        self.capture_class = None
        self.capture_text = ''
        self.li_items = []
        self.in_li = False
        self.li_text = ''
        self.li_model = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'tr':
            self.current_row = []
        elif tag in ('td', 'th') and self.current_row is not None:
            self.in_cell = True
            self.cell_text = ''
        elif tag == 'div' and attrs.get('class') == 'item':
            self.current_item = {}
        elif self.current_item is not None and tag in ('h2', 'p'):
            self.capture_tag = tag
            self.capture_class = attrs.get('class')
            self.capture_text = ''
        elif tag == 'li':
            self.in_li = True
            self.li_text = ''
            self.li_model = attrs.get('data-model')

    def handle_data(self, data):
        if self.in_cell:
            self.cell_text += data
        if self.capture_tag:
            self.capture_text += data
        if self.in_li:
            self.li_text += data

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self.in_cell:
            self.current_row.append(self.cell_text.strip())
            self.in_cell = False
            self.cell_text = ''
        elif tag == 'tr' and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None
        elif self.current_item is not None and self.capture_tag == tag:
            text = self.capture_text.strip()
            if tag == 'h2':
                self.current_item['model'] = text
            elif self.capture_class == 'price':
                self.current_item['price'] = text
            elif self.capture_class == 'mem':
                self.current_item['mem'] = text
            self.capture_tag = None
            self.capture_class = None
            self.capture_text = ''
        elif tag == 'div' and self.current_item is not None:
            if self.current_item:
                self.items.append(self.current_item)
            self.current_item = None
        elif tag == 'li' and self.in_li:
            self.li_items.append({'model': self.li_model, 'text': self.li_text.strip()})
            self.in_li = False
            self.li_text = ''
            self.li_model = None

def currency_and_price(s):
    s = s.strip()
    # Longest/specific symbols first.
    if s.startswith('NT$'):
        currency = 'NT$'
        raw = s[3:]
    elif s.startswith('USD'):
        currency = 'USD'
        raw = s[3:].strip()
    elif s.startswith('€'):
        currency = '€'
        raw = s[1:]
    else:
        m = re.match(r'([^\d\-+.,]+)?\s*(.*)', s)
        currency = (m.group(1) or '').strip()
        raw = m.group(2).strip()

    raw = raw.strip()
    # Convert both US style (1,250.00) and European style (1.299,00).
    if ',' in raw and '.' in raw:
        if raw.rfind(',') > raw.rfind('.'):
            normalized = raw.replace('.', '').replace(',', '.')
        else:
            normalized = raw.replace(',', '')
    elif ',' in raw:
        parts = raw.split(',')
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            normalized = raw.replace(',', '')
        else:
            normalized = raw.replace(',', '.')
    else:
        normalized = raw
    return currency, float(normalized)

def memory_gb(s):
    s = s.strip()
    m = re.search(r'([\d.]+)\s*(GB|MB)', s, re.I)
    if not m:
        raise ValueError(f'Cannot parse memory: {s}')
    val = float(m.group(1))
    unit = m.group(2).upper()
    gb = val if unit == 'GB' else val / 1024.0
    return int(gb) if gb.is_integer() else gb

records = []
for url in URLS:
    with urlopen(url, timeout=10) as resp:
        html = resp.read().decode('utf-8')
    parser = SimpleHTML()
    parser.feed(html)

    if url.endswith('/a'):
        for row in parser.rows[1:]:
            if len(row) >= 3:
                cur, price = currency_and_price(row[1])
                records.append({
                    'Model': row[0],
                    'Price': price,
                    'Currency': cur,
                    'MemoryGB': memory_gb(row[2]),
                    'SourceURL': url,
                })
    elif url.endswith('/b'):
        for item in parser.items:
            cur, price = currency_and_price(item['price'])
            records.append({
                'Model': item['model'],
                'Price': price,
                'Currency': cur,
                'MemoryGB': memory_gb(item['mem']),
                'SourceURL': url,
            })
    elif url.endswith('/c'):
        for li in parser.li_items:
            parts = [p.strip() for p in li['text'].split('—')]
            model = li['model'] or parts[0]
            price_text = parts[1]
            mem_text = parts[2]
            cur, price = currency_and_price(price_text)
            records.append({
                'Model': model,
                'Price': price,
                'Currency': cur,
                'MemoryGB': memory_gb(mem_text),
                'SourceURL': url,
            })

fields = ['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL']
# CSV
csv_path = OUT / 'merged_catalog.csv'
with csv_path.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    writer.writerows(records)

# XLSX for convenient review
xlsx_path = OUT / 'merged_catalog.xlsx'
wb = Workbook()
ws = wb.active
ws.title = 'MergedCatalog'
ws.append(fields)
for r in records:
    ws.append([r[f] for f in fields])
for col in ws.columns:
    max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
    ws.column_dimensions[col[0].column_letter].width = max_len + 2
wb.save(xlsx_path)

print(f'Wrote {len(records)} records')
print(csv_path)
print(xlsx_path)
print('\nCSV preview:')
print(csv_path.read_text(encoding='utf-8-sig'))
