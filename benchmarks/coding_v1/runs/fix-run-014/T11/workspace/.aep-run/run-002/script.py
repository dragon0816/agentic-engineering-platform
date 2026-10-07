from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urljoin
from html.parser import HTMLParser
from html import unescape
import re
from openpyxl import Workbook, load_workbook

BASE_LIST_URL = 'http://127.0.0.1:63668/t11/list'
OUTPUT = Path('output') / 'details.xlsx'
COLUMNS = ['Name', 'Price', 'Currency', 'CPU', 'MemoryGB', 'URL']

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            attrs = dict(attrs)
            self._href = attrs.get('href')
            self._text = []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self._href is not None:
            self.links.append((self._href, ' '.join(t.strip() for t in self._text if t.strip())))
            self._href = None
            self._text = []

class TextExtractor(HTMLParser):
    BLOCK_TAGS = {'p','div','li','tr','td','th','dt','dd','br','h1','h2','h3','section','article'}
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
        self.parts.append(data)
    def text(self):
        s = unescape(''.join(self.parts))
        lines = [re.sub(r'\s+', ' ', line).strip() for line in s.splitlines()]
        return '\n'.join(line for line in lines if line)

def fetch(url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(req, timeout=10) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or 'utf-8'
        return raw.decode(charset, errors='replace')

def strip_tags(fragment):
    text = re.sub(r'(?is)<(script|style).*?</\1>', ' ', fragment)
    text = re.sub(r'(?s)<[^>]+>', ' ', text)
    return re.sub(r'\s+', ' ', unescape(text)).strip()

def first_match(patterns, html, flags=re.I|re.S):
    for pat in patterns:
        m = re.search(pat, html, flags)
        if m:
            return strip_tags(m.group(1))
    return ''

def normalize_key(k):
    return re.sub(r'[^a-z0-9]+', '', k.lower())

def html_key_values(html):
    kv = {}
    # table rows: <tr><th>Name</th><td>...</td></tr> or td/td
    for m in re.finditer(r'(?is)<tr[^>]*>\s*<(?:th|td)[^>]*>(.*?)</(?:th|td)>\s*<(?:td|th)[^>]*>(.*?)</(?:td|th)>\s*</tr>', html):
        key = strip_tags(m.group(1))
        val = strip_tags(m.group(2))
        if key:
            kv[normalize_key(key)] = val
    # definition lists
    for m in re.finditer(r'(?is)<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>', html):
        key = strip_tags(m.group(1))
        val = strip_tags(m.group(2))
        if key:
            kv[normalize_key(key)] = val
    # common label/value div or span pairs with colon in visible text are handled later from text lines
    return kv

def text_key_values(text):
    kv = {}
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for i, line in enumerate(lines):
        if ':' in line:
            k, v = line.split(':', 1)
            if k.strip() and len(k.strip()) <= 40:
                kv.setdefault(normalize_key(k), v.strip())
        elif i + 1 < len(lines) and normalize_key(line) in {'name','price','currency','cpu','memory','memorygb','ram'}:
            kv.setdefault(normalize_key(line), lines[i+1].strip())
    return kv

def get_kv(kv, *keys):
    for key in keys:
        nk = normalize_key(key)
        if nk in kv and kv[nk] != '':
            return kv[nk]
    return ''

def parse_price_currency(value):
    value = (value or '').strip()
    if not value:
        return '', ''
    # Currency may be a symbol, code, or prefix/suffix.
    symbol_map = {'$':'USD', '€':'EUR', '£':'GBP', '¥':'JPY', 'NT$':'TWD'}
    currency = ''
    for sym, code in symbol_map.items():
        if sym in value:
            currency = code
            break
    code_match = re.search(r'\b([A-Z]{3})\b', value)
    if code_match:
        currency = code_match.group(1)
    num_match = re.search(r'[-+]?\d[\d,]*(?:\.\d+)?', value)
    price = num_match.group(0).replace(',', '') if num_match else value
    return price, currency

def normalize_memory_to_gb(value):
    value = (value or '').strip()
    if not value:
        return ''
    m = re.search(r'(\d+(?:\.\d+)?)\s*(TiB|TB|GiB|GB|MiB|MB)\b', value, re.I)
    if not m:
        m = re.search(r'(\d+(?:\.\d+)?)', value)
        return m.group(1) if m else value
    n = float(m.group(1))
    unit = m.group(2).lower()
    if unit in {'tb', 'tib'}:
        gb = n * 1024
    elif unit in {'mb', 'mib'}:
        gb = n / 1024
    else:
        gb = n
    if abs(gb - round(gb)) < 1e-9:
        return str(int(round(gb)))
    return ('%.6f' % gb).rstrip('0').rstrip('.')

def parse_detail(url, html, fallback_name=''):
    text_parser = TextExtractor()
    text_parser.feed(html)
    text = text_parser.text()
    kv = html_key_values(html)
    kv.update({k:v for k,v in text_key_values(text).items() if k not in kv})

    name = get_kv(kv, 'Name', 'Product Name')
    if not name:
        name = first_match([
            r'<h1[^>]*>(.*?)</h1>',
            r'<[^>]+class=["\'][^"\']*(?:name|product-name|title)[^"\']*["\'][^>]*>(.*?)</[^>]+>',
            r'<title[^>]*>(.*?)</title>',
        ], html)
    if not name:
        name = fallback_name
    name = re.sub(r'\s*[-|]\s*(?:Detail|Product).*$', '', name, flags=re.I).strip()

    cpu = get_kv(kv, 'CPU', 'Processor')
    memory = get_kv(kv, 'MemoryGB', 'Memory GB', 'Memory', 'RAM')
    memory_gb = normalize_memory_to_gb(memory)

    price = get_kv(kv, 'Price')
    currency = get_kv(kv, 'Currency')
    if not price:
        price = first_match([
            r'<[^>]+class=["\'][^"\']*price[^"\']*["\'][^>]*>(.*?)</[^>]+>',
            r'<[^>]+id=["\'][^"\']*price[^"\']*["\'][^>]*>(.*?)</[^>]+>',
        ], html)
    parsed_price, parsed_currency = parse_price_currency(price)
    if parsed_price:
        price = parsed_price
    if not currency and parsed_currency:
        currency = parsed_currency
    if not currency:
        currency = first_match([
            r'<[^>]+class=["\'][^"\']*currency[^"\']*["\'][^>]*>(.*?)</[^>]+>',
            r'<[^>]+id=["\'][^"\']*currency[^"\']*["\'][^>]*>(.*?)</[^>]+>',
        ], html)
    currency = currency.strip()

    return {'Name': name, 'Price': price, 'Currency': currency, 'CPU': cpu, 'MemoryGB': memory_gb, 'URL': url}, text

# Discover links from list page.
list_html = fetch(BASE_LIST_URL)
print('Fetched list page:', BASE_LIST_URL, 'chars=', len(list_html))
print('List markup sample:', list_html[:500])
link_parser = LinkParser()
link_parser.feed(list_html)
links = []
seen = set()
for href, label in link_parser.links:
    if href and '/t11/item/' in href:
        abs_url = urljoin(BASE_LIST_URL, href)
        if abs_url not in seen:
            links.append((abs_url, label))
            seen.add(abs_url)
print('Detail links found:', len(links))
for u, label in links:
    print(' -', u, 'label=', label)

rows = []
for idx, (url, label) in enumerate(links, start=1):
    html = fetch(url)
    print(f'Fetched detail {idx}: {url} chars={len(html)} sample={html[:300]!r}')
    row, text = parse_detail(url, html, label)
    print(' Parsed:', row)
    rows.append(row)

# Write workbook.
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
wb = Workbook()
ws = wb.active
ws.title = 'details'
ws.append(COLUMNS)
for row in rows:
    values = [row.get(c, '') for c in COLUMNS]
    # Store price and MemoryGB as numbers when they are numeric, blank otherwise.
    out = []
    for c, v in zip(COLUMNS, values):
        if c in {'Price', 'MemoryGB'} and isinstance(v, str) and re.fullmatch(r'[-+]?\d+(?:\.\d+)?', v):
            num = float(v)
            out.append(int(num) if num.is_integer() else num)
        else:
            out.append(v if v is not None else '')
    ws.append(out)
wb.save(OUTPUT)
print('Saved:', OUTPUT)

# Reopen and verify requirements.
wb2 = load_workbook(OUTPUT, data_only=True)
ws2 = wb2['details']
headers = [cell.value for cell in ws2[1]]
assert headers == COLUMNS, f'Unexpected headers: {headers}'
data_rows = list(ws2.iter_rows(min_row=2, values_only=True))
assert len(data_rows) == len(links), f'Row count {len(data_rows)} != links {len(links)}'
for r_idx, row in enumerate(data_rows, start=2):
    rec = dict(zip(COLUMNS, row))
    assert rec['URL'] and str(rec['URL']).startswith('http://127.0.0.1:63668/t11/item/'), f'Bad URL row {r_idx}: {rec["URL"]}'
    for c in COLUMNS:
        assert c in rec
    mem = rec['MemoryGB']
    assert mem is None or isinstance(mem, (int, float, str)), f'Bad MemoryGB type row {r_idx}'
    if isinstance(mem, str) and mem:
        assert re.fullmatch(r'[-+]?\d+(?:\.\d+)?', mem), f'MemoryGB not normalized row {r_idx}: {mem}'
print('Verified output workbook: file exists, sheet details, exact columns, one row per detail link, URL values, and MemoryGB normalized/blank.')
print('Rows written:')
for row in data_rows:
    print(row)