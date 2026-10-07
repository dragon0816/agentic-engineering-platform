from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
from html import unescape
import re
import openpyxl

BASE_LIST_URL = 'http://127.0.0.1:50351/t11/list'
OUTPUT = Path('output') / 'details.xlsx'
HEADERS = ['Name', 'Price', 'Currency', 'CPU', 'MemoryGB', 'URL']

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._current_href = None
        self._text = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            attrs = dict(attrs)
            self._current_href = attrs.get('href')
            self._text = []
    def handle_data(self, data):
        if self._current_href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self._current_href is not None:
            self.links.append((self._current_href, ''.join(self._text).strip()))
            self._current_href = None
            self._text = []

class TextParser(HTMLParser):
    BLOCK_TAGS = {'p','div','li','tr','td','th','dt','dd','br','h1','h2','h3','h4','h5','h6','span'}
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag.lower() in self.BLOCK_TAGS:
            self.parts.append('\n')
    def handle_data(self, data):
        if data:
            self.parts.append(data)
    def text(self):
        s = unescape(''.join(self.parts))
        lines = [' '.join(line.split()) for line in s.splitlines()]
        return '\n'.join(line for line in lines if line)

def fetch(url):
    with urlopen(url, timeout=10) as r:
        return r.read().decode('utf-8', errors='replace')

def page_text(html):
    p = TextParser()
    p.feed(html)
    return p.text()

def normalize_key(k):
    return re.sub(r'[^a-z0-9]', '', k.lower())

def extract_pairs(text):
    pairs = {}
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Parse common formats: "Name: Laptop", "Price 1299 USD", tables rendered line-by-line.
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r'^([^:：]+)\s*[:：]\s*(.*)$', line)
        if m:
            key = normalize_key(m.group(1))
            val = m.group(2).strip()
            pairs[key] = val
            i += 1
            continue
        keynorm = normalize_key(line)
        if keynorm in {'name','price','currency','cpu','memory','memorygb','ram'} and i + 1 < len(lines):
            pairs[keynorm] = lines[i+1].strip()
            i += 2
            continue
        i += 1
    return pairs

def parse_price_currency(raw):
    price = ''
    currency = ''
    if raw is None:
        return price, currency
    s = str(raw).strip()
    if not s:
        return price, currency
    # Currency code/symbol may appear before or after the number.
    num_match = re.search(r'[-+]?\d[\d,]*(?:\.\d+)?', s)
    if num_match:
        price = num_match.group(0).replace(',', '')
        before = s[:num_match.start()].strip()
        after = s[num_match.end():].strip()
        cur = (before or after).strip()
        cur = re.sub(r'^[\s:：-]+|[\s:：-]+$', '', cur)
        currency = cur
    else:
        price = s
    return price, currency

def normalize_memory_gb(raw):
    if raw is None:
        return ''
    s = str(raw).strip()
    if not s:
        return ''
    m = re.search(r'([-+]?\d+(?:\.\d+)?)\s*([kmgt]?i?b|[kmgt]b|[kmgt])?', s, re.I)
    if not m:
        return s
    val = float(m.group(1))
    unit = (m.group(2) or 'GB').upper().replace('IB','B')
    if unit in {'G','GB'}:
        gb = val
    elif unit in {'M','MB'}:
        gb = val / 1024
    elif unit in {'K','KB'}:
        gb = val / (1024*1024)
    elif unit in {'T','TB'}:
        gb = val * 1024
    else:
        gb = val
    if abs(gb - round(gb)) < 1e-9:
        return int(round(gb))
    return round(gb, 6)

def first_value(pairs, *keys):
    for k in keys:
        nk = normalize_key(k)
        if nk in pairs and pairs[nk] != '':
            return pairs[nk]
    return ''

# 1) Read list and find detail links.
list_html = fetch(BASE_LIST_URL)
link_parser = LinkParser()
link_parser.feed(list_html)
links = []
seen = set()
for href, label in link_parser.links:
    abs_url = urljoin(BASE_LIST_URL, href)
    if '/t11/item/' in abs_url and abs_url not in seen:
        links.append((abs_url, label))
        seen.add(abs_url)

print(f'Found {len(links)} detail links:')
for u, label in links:
    print(' -', label, u)

rows = []
print('\nDetail page samples and parsed values:')
for url, label in links:
    html = fetch(url)
    text = page_text(html)
    print('\nURL:', url)
    print('TEXT SAMPLE:', text[:1000])
    pairs = extract_pairs(text)

    # Also parse meta-ish html attributes if fields are in simple tags with class/id names.
    attr_values = {}
    for field in ['name','price','currency','cpu','memory','memorygb','ram']:
        patterns = [
            rf'<[^>]+(?:id|class)=["\'][^"\']*{field}[^"\']*["\'][^>]*>(.*?)</[^>]+>',
            rf'<[^>]+(?:data-field|data-key|name)=["\']{field}["\'][^>]*>(.*?)</[^>]+>',
        ]
        for pat in patterns:
            mm = re.search(pat, html, re.I | re.S)
            if mm:
                clean = page_text(mm.group(1)) or re.sub('<[^>]+>', '', mm.group(1))
                attr_values[normalize_key(field)] = clean.strip()
                break
    pairs.update({k:v for k,v in attr_values.items() if v})

    name = first_value(pairs, 'Name') or label
    cpu = first_value(pairs, 'CPU', 'Processor')
    mem_raw = first_value(pairs, 'MemoryGB', 'Memory', 'RAM')
    memory_gb = normalize_memory_gb(mem_raw)
    price_raw = first_value(pairs, 'Price')
    price, currency_from_price = parse_price_currency(price_raw)
    currency = first_value(pairs, 'Currency') or currency_from_price

    row = {
        'Name': name,
        'Price': price,
        'Currency': currency,
        'CPU': cpu,
        'MemoryGB': memory_gb,
        'URL': url,
    }
    print('PARSED:', row)
    rows.append(row)

# 2) Write workbook.
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'details'
ws.append(HEADERS)
for row in rows:
    ws.append([row[h] for h in HEADERS])
for col in range(1, len(HEADERS)+1):
    ws.cell(row=1, column=col).style = 'Headline 3'
    max_len = max(len(str(ws.cell(row=r, column=col).value or '')) for r in range(1, ws.max_row+1))
    ws.column_dimensions[openpyxl.utils.get_column_letter(col)].width = min(max(max_len + 2, 12), 60)
wb.save(OUTPUT)
print('\nWrote', OUTPUT)

# 3) Reopen and verify all stated requirements.
check_wb = openpyxl.load_workbook(OUTPUT, data_only=True)
check_ws = check_wb.active
headers = [check_ws.cell(1, c).value for c in range(1, check_ws.max_column+1)]
assert headers == HEADERS, f'headers mismatch: {headers}'
assert check_ws.max_row == len(rows) + 1, f'row count mismatch: {check_ws.max_row} vs {len(rows)+1}'
for r in range(2, check_ws.max_row + 1):
    vals = {HEADERS[c-1]: check_ws.cell(r, c).value for c in range(1, len(HEADERS)+1)}
    assert vals['URL'] and str(vals['URL']).startswith('http://127.0.0.1:50351/t11/item/'), f'bad URL row {r}: {vals}'
    mem = vals['MemoryGB']
    if mem not in (None, ''):
        assert isinstance(mem, (int, float)), f'MemoryGB not numeric or blank at row {r}: {mem!r}'
    # Missing fields are allowed to remain blank/None.
print('Verified output file:', OUTPUT)
print('Verified headers:', headers)
print('Verified data rows:', check_ws.max_row - 1)
print('Verified MemoryGB values are numeric when present and blank allowed for missing fields.')
print('Output rows:')
for r in range(2, check_ws.max_row + 1):
    print([check_ws.cell(r, c).value for c in range(1, len(HEADERS)+1)])