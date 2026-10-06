import os, re, urllib.request, urllib.parse, html
from html.parser import HTMLParser
from pathlib import Path
from openpyxl import Workbook, load_workbook

BASE_LIST_URL = 'http://127.0.0.1:49758/t11/list'
WORKSPACE = Path.cwd()
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(parents=True, exist_ok=True)
OUTFILE = OUTPUT / 'details.xlsx'

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]; self._href=None; self._text=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='a':
            self._href=dict(attrs).get('href'); self._text=[]
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower()=='a' and self._href is not None:
            self.links.append((self._href, ''.join(self._text).strip()))
            self._href=None; self._text=[]

class H1Parser(HTMLParser):
    def __init__(self):
        super().__init__(); self.in_h1=False; self.h1=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='h1': self.in_h1=True
    def handle_data(self, data):
        if self.in_h1: self.h1.append(data)
    def handle_endtag(self, tag):
        if tag.lower()=='h1': self.in_h1=False
    def value(self):
        return clean_value(''.join(self.h1))

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts=[]
    def handle_data(self, data):
        s=data.strip()
        if s: self.parts.append(s)
    def text(self): return '\n'.join(self.parts)

def fetch(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.read().decode('utf-8', errors='replace')

def clean_value(v):
    if v is None: return ''
    v=html.unescape(str(v)).strip()
    v=re.sub(r'\s+', ' ', v)
    return v.strip(' :-\t\r\n')

def page_text(markup):
    p=TextParser(); p.feed(markup); return p.text()

def parse_labeled_values(markup):
    data={}
    labels={'name':'Name','price':'Price','currency':'Currency','cpu':'CPU','memory':'Memory','memorygb':'MemoryGB','memory gb':'MemoryGB'}
    # Exact table row parsing.
    for m in re.finditer(r'(?is)<tr[^>]*>\s*<t[dh][^>]*>(.*?)</t[dh]>\s*<td[^>]*>(.*?)</td>\s*</tr>', markup):
        k=clean_value(re.sub(r'<[^>]+>', ' ', m.group(1)))
        v=clean_value(re.sub(r'<[^>]+>', ' ', m.group(2)))
        kl=re.sub(r'\s+', ' ', k.lower())
        if kl in labels or kl.replace(' ','') in labels:
            data[labels.get(kl, labels.get(kl.replace(' ', ''), k))]=v
    # H1 is product name if Name label is absent.
    h=H1Parser(); h.feed(markup)
    if h.value() and 'Name' not in data:
        data['Name']=h.value()
    # Fallback line parser for non-table pages.
    s=re.sub(r'(?i)<\s*br\s*/?\s*>', '\n', markup)
    s=re.sub(r'(?i)</\s*(li|p|div|tr|h[1-6]|dt|dd)\s*>', '\n', s)
    txt=page_text(s)
    for line in [clean_value(x) for x in txt.splitlines() if clean_value(x)]:
        m=re.match(r'^(Name|Price|Currency|CPU|MemoryGB|Memory\s*GB|Memory)\s*[:：\-]\s*(.+)$', line, re.I)
        if m:
            key_raw=re.sub(r'\s+', ' ', m.group(1).lower())
            key=labels.get(key_raw, labels.get(key_raw.replace(' ', ''), m.group(1)))
            data.setdefault(key, clean_value(m.group(2)))
    return data, txt

def normalize_memory_gb(raw):
    raw=clean_value(raw)
    if not raw: return ''
    m=re.search(r'([0-9]+(?:\.[0-9]+)?)', raw.replace(',', ''))
    if not m: return ''
    val=float(m.group(1)); lower=raw.lower()
    if re.search(r'\btb\b|terabyte', lower): val*=1024
    elif re.search(r'\bmb\b|megabyte', lower): val/=1024
    return int(round(val)) if abs(val-round(val))<1e-9 else val

def normalize_price(raw):
    raw=clean_value(raw)
    if not raw: return ''
    m=re.search(r'-?\d+(?:,\d{3})*(?:\.\d+)?|-?\d+(?:\.\d+)?', raw)
    if not m: return raw
    try:
        f=float(m.group(0).replace(',', ''))
        return int(f) if f.is_integer() else f
    except ValueError:
        return m.group(0).replace(',', '')

def detect_currency(price_raw, currency_raw):
    currency=clean_value(currency_raw)
    if currency: return currency
    raw=clean_value(price_raw)
    up=raw.upper()
    # Prefer explicit multi-character symbols before the generic '$'.
    if re.search(r'\b(TWD|NTD)\b|NT\$', up): return 'TWD'
    if re.search(r'\bUSD\b|US\$', up): return 'USD'
    if re.search(r'\bEUR\b|€', up): return 'EUR'
    if re.search(r'\bGBP\b|£', up): return 'GBP'
    if re.search(r'\bJPY\b|¥', up): return 'JPY'
    if '$' in raw: return 'USD'
    return ''

print('Fetching list:', BASE_LIST_URL)
list_html=fetch(BASE_LIST_URL)
p=LinkParser(); p.feed(list_html)
item_urls=[]
for href,label in p.links:
    full=urllib.parse.urljoin(BASE_LIST_URL, href)
    if '/t11/item/' in full and full not in item_urls:
        item_urls.append(full)
print('Found detail URLs:', item_urls)

headers=['Name','Price','Currency','CPU','MemoryGB','URL']
rows=[]
for url in item_urls:
    markup=fetch(url)
    print('\nDETAIL', url, 'first 600 chars:\n', markup[:600])
    data, txt=parse_labeled_values(markup)
    print('Parsed data:', data)
    row={
        'Name': clean_value(data.get('Name','')),
        'Price': normalize_price(data.get('Price','')),
        'Currency': detect_currency(data.get('Price',''), data.get('Currency','')),
        'CPU': clean_value(data.get('CPU','')),
        'MemoryGB': normalize_memory_gb(data.get('MemoryGB') or data.get('Memory','')),
        'URL': url,
    }
    rows.append(row)

wb=Workbook(); ws=wb.active; ws.title='details'; ws.append(headers)
for row in rows:
    ws.append([row[h] for h in headers])
wb.save(OUTFILE)
print('\nWrote', OUTFILE)

# Verification from saved output.
wb2=load_workbook(OUTFILE, data_only=True)
ws2=wb2['details']
out_headers=[c.value for c in ws2[1]]
out_rows=list(ws2.iter_rows(min_row=2, values_only=True))
print('CHECK headers:', out_headers)
print('CHECK row_count:', len(out_rows), 'expected:', len(item_urls))
print('CHECK rows:')
for r in out_rows: print(r)
assert out_headers==headers
assert len(out_rows)==len(item_urls)
for name,price,currency,cpu,mem,url in out_rows:
    assert isinstance(name, str) and name.strip(), f'Name missing: {name!r}'
    if price is not None: assert isinstance(price, (int,float)), f'Price not numeric: {price!r}'
    if currency is not None: assert isinstance(currency, str), f'Currency not text: {currency!r}'
    if cpu is not None: assert isinstance(cpu, str), f'CPU not text: {cpu!r}'
    if mem is not None: assert isinstance(mem, (int,float)), f'MemoryGB not numeric: {mem!r}'
    assert isinstance(url, str) and url.startswith('http://127.0.0.1:49758/t11/item/')
print('CHECK passed: saved details.xlsx has requested columns, 4 detail rows, Name/URL text, numeric Price and MemoryGB where present, text Currency/CPU where present, and blank cells for missing fields.')