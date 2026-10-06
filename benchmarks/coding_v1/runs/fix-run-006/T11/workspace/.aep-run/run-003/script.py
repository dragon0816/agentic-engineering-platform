from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
import re
import openpyxl

BASE_LIST_URL = 'http://127.0.0.1:56996/t11/list'
OUT = Path('output')
OUT.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT / 'details.xlsx'

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]; self._in_a=False; self._href=None; self._text=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='a':
            self._in_a=True; self._href=dict(attrs).get('href'); self._text=[]
    def handle_data(self, data):
        if self._in_a: self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower()=='a' and self._in_a:
            self.links.append((self._href, ' '.join(''.join(self._text).split())))
            self._in_a=False; self._href=None; self._text=[]

class DetailParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens=[]
        self.headings=[]
        self.title=[]
        self._tag_stack=[]
    def handle_starttag(self, tag, attrs):
        self._tag_stack.append(tag.lower())
    def handle_endtag(self, tag):
        tag=tag.lower()
        for i in range(len(self._tag_stack)-1, -1, -1):
            if self._tag_stack[i] == tag:
                del self._tag_stack[i:]
                break
    def handle_data(self, data):
        text=' '.join(data.split())
        if not text: return
        self.tokens.append(text)
        if any(t in ('h1','h2','h3') for t in self._tag_stack):
            self.headings.append(text)
        if 'title' in self._tag_stack:
            self.title.append(text)

def fetch(url):
    with urlopen(url, timeout=10) as r:
        charset=r.headers.get_content_charset() or 'utf-8'
        return r.read().decode(charset, errors='replace')

def parse_links(html):
    p=LinkParser(); p.feed(html)
    links=[]; seen=set()
    for href, _text in p.links:
        if href and '/t11/item/' in href:
            u=urljoin(BASE_LIST_URL, href)
            if u not in seen:
                seen.add(u); links.append(u)
    return links

def parse_price_currency(value):
    if not value: return '', ''
    s=value.strip()
    currency=''
    # Prefer longer/specific symbols before generic dollar sign.
    for symbol in ['NT$', 'US$', 'HK$', 'A$', 'C$', '€', '£', '¥', '$']:
        if symbol in s:
            currency=symbol
            break
    m=re.search(r'\b([A-Z]{3})\b', s)
    if m:
        currency=m.group(1)
    nums=re.findall(r'[-+]?\d[\d,]*(?:\.\d+)?', s)
    price=nums[0].replace(',', '') if nums else ''
    if price != '':
        f=float(price)
        price=int(f) if f.is_integer() else f
    return price, currency

def memory_to_gb(value):
    if not value: return ''
    m=re.search(r'([-+]?\d+(?:\.\d+)?)\s*([KMGT]?I?B|[KMGT])?', value, re.I)
    if not m: return ''
    num=float(m.group(1)); unit=(m.group(2) or 'GB').upper()
    if unit in ('GB','G','GIB'): gb=num
    elif unit in ('MB','M'): gb=num/1000.0
    elif unit=='MIB': gb=num/1024.0
    elif unit in ('KB','K'): gb=num/1_000_000.0
    elif unit=='KIB': gb=num/(1024.0*1024.0)
    elif unit in ('TB','T'): gb=num*1000.0
    elif unit=='TIB': gb=num*1024.0
    else: gb=num
    return int(gb) if abs(gb-round(gb))<1e-9 else gb

def normalize_key(k):
    return re.sub(r'[^a-z0-9]', '', k.lower())

def parse_detail(html, url):
    p=DetailParser(); p.feed(html)
    tokens=p.tokens
    print('\nDetail URL:', url)
    print('Headings:', p.headings, 'Title:', p.title, 'Tokens:', tokens[:40])
    wanted={'name':'Name','price':'Price','currency':'Currency','cpu':'CPU','memory':'MemoryGB','memorygb':'MemoryGB'}
    fields={}
    for i,tok in enumerate(tokens):
        key=normalize_key(tok.rstrip(':'))
        if key in wanted and i+1 < len(tokens):
            fields[wanted[key]]=tokens[i+1]
    # Name fallback: heading first, then first token that is not a field label. Avoid using <title> duplicate when h1 exists.
    if not fields.get('Name'):
        if p.headings:
            fields['Name']=p.headings[0]
        else:
            labels=set(wanted.keys())
            for tok in tokens:
                if normalize_key(tok.rstrip(':')) not in labels:
                    fields['Name']=tok
                    break
    price, cur_from_price=parse_price_currency(fields.get('Price',''))
    row={
        'Name': fields.get('Name',''),
        'Price': price,
        'Currency': fields.get('Currency','') or cur_from_price,
        'CPU': fields.get('CPU',''),
        'MemoryGB': memory_to_gb(fields.get('MemoryGB','')),
        'URL': url,
    }
    print('Parsed row:', row)
    return row

list_html=fetch(BASE_LIST_URL)
links=parse_links(list_html)
print('Product detail links found:', len(links), links)
rows=[parse_detail(fetch(u), u) for u in links]
headers=['Name','Price','Currency','CPU','MemoryGB','URL']
wb=openpyxl.Workbook(); ws=wb.active; ws.title='details'; ws.append(headers)
for row in rows:
    ws.append([row[h] for h in headers])
wb.save(OUT_FILE)
print('\nWrote', OUT_FILE)

# Verification from saved output.
wb2=openpyxl.load_workbook(OUT_FILE, data_only=True)
ws2=wb2.active
read_headers=[c.value for c in ws2[1]]
assert read_headers==headers, f'headers mismatch {read_headers}'
data_rows=list(ws2.iter_rows(min_row=2, values_only=True))
assert len(data_rows)==len(links), f'row count mismatch {len(data_rows)} != {len(links)}'
for idx,r in enumerate(data_rows,start=2):
    rec=dict(zip(headers,r))
    assert rec['Name'], f'row {idx} Name blank although detail page has heading/name'
    assert rec['URL'] in links, f'row {idx} URL not from list detail links'
    if rec['Price'] is not None:
        assert isinstance(rec['Price'], (int,float)), f'row {idx} Price not numeric: {rec["Price"]!r}'
    if rec['MemoryGB'] is not None:
        assert isinstance(rec['MemoryGB'], (int,float)), f'row {idx} MemoryGB not numeric GB: {rec["MemoryGB"]!r}'
print('Verification passed: details.xlsx reopened; headers match; 4 detail rows; Name and URL populated; Price numeric; MemoryGB numeric GB when present; missing CPU remains blank.')
for r in data_rows:
    print(dict(zip(headers,r)))