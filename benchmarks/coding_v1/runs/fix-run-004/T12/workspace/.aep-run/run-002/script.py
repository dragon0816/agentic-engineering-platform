from pathlib import Path
from urllib.request import urlopen
from html.parser import HTMLParser
import csv
import json
import re

WORKSPACE = Path.cwd()
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(parents=True, exist_ok=True)

urls = [
    'http://127.0.0.1:58649/t12/a',
    'http://127.0.0.1:58649/t12/b',
    'http://127.0.0.1:58649/t12/c',
]

print('Workspace:', WORKSPACE)
print('Input files:')
for p in sorted((WORKSPACE / 'input').glob('**/*')):
    print(' -', p.relative_to(WORKSPACE), 'file' if p.is_file() else 'dir')

pages = {}
for url in urls:
    with urlopen(url, timeout=10) as r:
        html = r.read().decode('utf-8', errors='replace')
        pages[url] = html
        print('\nFetched', url)
        print('  status:', getattr(r, 'status', None), 'content-type:', r.headers.get('content-type'))
        print('  sample:', html[:220].replace('\n', ' '))

class Node:
    def __init__(self, tag=None, attrs=None, parent=None):
        self.tag = tag
        self.attrs = dict(attrs or [])
        self.parent = parent
        self.children = []
        self.text_parts = []
    def text(self):
        parts = list(self.text_parts)
        for c in self.children:
            parts.append(c.text())
        return ''.join(parts)
    def find_all(self, tag=None, **attrs):
        out = []
        if (tag is None or self.tag == tag):
            ok = True
            for k, v in attrs.items():
                if self.attrs.get(k) != v:
                    ok = False
                    break
            if ok:
                out.append(self)
        for c in self.children:
            out.extend(c.find_all(tag, **attrs))
        return out

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.root = Node('root')
        self.stack = [self.root]
    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.stack[-1])
        self.stack[-1].children.append(n)
        self.stack.append(n)
    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break
    def handle_data(self, data):
        self.stack[-1].text_parts.append(data)

def parse_dom(html):
    p = Parser()
    p.feed(html)
    return p.root

def parse_price(s):
    s = s.strip()
    # Currency: keep the source currency token/symbol, while Price is numeric only.
    if 'NT$' in s:
        currency = 'NT$'
        num = s.replace('NT$', '')
    elif 'USD' in s:
        currency = 'USD'
        num = s.replace('USD', '')
    elif '€' in s:
        currency = '€'
        num = s.replace('€', '')
    else:
        m = re.match(r'([^\d.,+-]+)?\s*(.*)', s)
        currency = (m.group(1) or '').strip()
        num = m.group(2)
    num = num.strip()
    # Handle both 1,250.00 and 1.299,00 formats.
    if ',' in num and '.' in num:
        if num.rfind(',') > num.rfind('.'):
            num = num.replace('.', '').replace(',', '.')
        else:
            num = num.replace(',', '')
    elif ',' in num:
        # Treat a lone comma followed by exactly 2 digits as decimal, otherwise thousands.
        if re.search(r',\d{2}$', num):
            num = num.replace(',', '.')
        else:
            num = num.replace(',', '')
    value = float(num)
    return value, currency

def parse_memory_gb(s):
    s = s.strip()
    m = re.search(r'([\d.]+)\s*(GB|MB)', s, flags=re.I)
    if not m:
        raise ValueError(f'Cannot parse memory: {s!r}')
    val = float(m.group(1))
    unit = m.group(2).upper()
    gb = val if unit == 'GB' else val / 1024.0
    return gb

rows = []
for url, html in pages.items():
    dom = parse_dom(html)
    if url.endswith('/a'):
        table = dom.find_all('table', id='p')[0]
        trs = table.find_all('tr')
        for tr in trs[1:]:
            tds = tr.find_all('td')
            model = tds[0].text().strip()
            price, currency = parse_price(tds[1].text())
            mem_gb = parse_memory_gb(tds[2].text())
            rows.append({'Model': model, 'Price': price, 'Currency': currency, 'MemoryGB': mem_gb, 'SourceURL': url})
    elif url.endswith('/b'):
        for item in dom.find_all('div', **{'class':'item'}):
            model = item.find_all('h2')[0].text().strip()
            price_text = item.find_all('p', **{'class':'price'})[0].text().strip()
            mem_text = item.find_all('p', **{'class':'mem'})[0].text().strip()
            price, currency = parse_price(price_text)
            mem_gb = parse_memory_gb(mem_text)
            rows.append({'Model': model, 'Price': price, 'Currency': currency, 'MemoryGB': mem_gb, 'SourceURL': url})
    elif url.endswith('/c'):
        for li in dom.find_all('li'):
            model = li.attrs.get('data-model', '').strip()
            text = ' '.join(li.text().split())
            parts = [part.strip() for part in text.split('—')]
            if not model:
                model = parts[0]
            price, currency = parse_price(parts[1])
            mem_gb = parse_memory_gb(parts[2])
            rows.append({'Model': model, 'Price': price, 'Currency': currency, 'MemoryGB': mem_gb, 'SourceURL': url})

fieldnames = ['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL']
csv_path = OUTPUT / 'merged_catalog.csv'
json_path = OUTPUT / 'merged_catalog.json'

with csv_path.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)

with json_path.open('w', encoding='utf-8') as f:
    json.dump(rows, f, ensure_ascii=False, indent=2)

# Reopen and verify output requirements.
expected = [
    {'Model':'NX-1','Price':12000.0,'Currency':'NT$','MemoryGB':16.0,'SourceURL':urls[0]},
    {'Model':'NX-2','Price':8500.0,'Currency':'NT$','MemoryGB':8.0,'SourceURL':urls[0]},
    {'Model':'NX-1','Price':399.50,'Currency':'USD','MemoryGB':16.0,'SourceURL':urls[1]},
    {'Model':'NX-3','Price':1250.0,'Currency':'USD','MemoryGB':32.0,'SourceURL':urls[1]},
    {'Model':'NX-4','Price':499.0,'Currency':'€','MemoryGB':4.0,'SourceURL':urls[2]},
    {'Model':'NX-5','Price':1299.0,'Currency':'€','MemoryGB':64.0,'SourceURL':urls[2]},
]

with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    read_rows = list(reader)
    assert reader.fieldnames == fieldnames, reader.fieldnames
    assert len(read_rows) == len(expected), len(read_rows)
    for actual, exp in zip(read_rows, expected):
        assert actual['Model'] == exp['Model']
        assert abs(float(actual['Price']) - exp['Price']) < 1e-9, actual
        assert actual['Currency'] == exp['Currency']
        assert abs(float(actual['MemoryGB']) - exp['MemoryGB']) < 1e-9, actual
        assert actual['SourceURL'] == exp['SourceURL']

with json_path.open('r', encoding='utf-8') as f:
    read_json = json.load(f)
    assert len(read_json) == len(expected), len(read_json)
    assert list(read_json[0].keys()) == fieldnames, read_json[0].keys()
    for actual, exp in zip(read_json, expected):
        assert actual['Model'] == exp['Model']
        assert isinstance(actual['Price'], (int, float)) and abs(float(actual['Price']) - exp['Price']) < 1e-9
        assert actual['Currency'] == exp['Currency']
        assert isinstance(actual['MemoryGB'], (int, float)) and abs(float(actual['MemoryGB']) - exp['MemoryGB']) < 1e-9
        assert actual['SourceURL'] == exp['SourceURL']

print('\nWrote outputs:')
print(' -', csv_path)
print(' -', json_path)
print('\nVerified:')
print(' - output files reopen successfully')
print(' - columns exactly:', fieldnames)
print(' - row count:', len(read_rows))
print(' - duplicate model NX-1 retained from different SourceURL values')
print(' - Price values are numeric after removing currency symbols/thousands separators')
print(' - Currency values retained without FX conversion')
print(' - MemoryGB converted with 1024 MB = 1 GB')
print('\nCSV preview:')
for r in read_rows:
    print(r)
