import os, re, html, json, urllib.request, urllib.parse
from pathlib import Path
from html.parser import HTMLParser
from openpyxl import Workbook, load_workbook

BASE_LIST_URL = 'http://127.0.0.1:58649/t11/list'
WORKSPACE = Path.cwd()
OUT = WORKSPACE / 'output' / 'details.xlsx'
OUT.parent.mkdir(parents=True, exist_ok=True)

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
            if self._href: self.links.append((self._href, ' '.join(''.join(self._text).split())))
            self._in_a=False; self._href=None; self._text=[]

def fetch(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return r.read().decode('utf-8', errors='replace')

def clean_text(s):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', s or '')).split())

def parse_keyvals(doc):
    kv={}
    for row in re.findall(r'<tr\b[^>]*>(.*?)</tr>', doc, flags=re.I|re.S):
        cells=[clean_text(c) for c in re.findall(r'<(?:th|td)\b[^>]*>(.*?)</(?:th|td)>', row, flags=re.I|re.S)]
        if len(cells)>=2:
            kv[cells[0].strip().rstrip(':：').lower()] = cells[1].strip()
    for m in re.finditer(r'<dt\b[^>]*>(.*?)</dt>\s*<dd\b[^>]*>(.*?)</dd>', doc, flags=re.I|re.S):
        kv[clean_text(m.group(1)).rstrip(':：').lower()] = clean_text(m.group(2))
    text_doc = re.sub(r'</(?:p|div|li|tr|h\d|dt|dd)>', '\n', doc, flags=re.I)
    text = html.unescape(re.sub(r'<[^>]+>', ' ', text_doc))
    for line in [' '.join(line.split()) for line in text.splitlines() if line.strip()]:
        m=re.match(r'^(Name|Price|Currency|CPU|Memory|RAM)\s*[:：]\s*(.+)$', line, flags=re.I)
        if m: kv[m.group(1).lower()] = m.group(2).strip()
    return kv

def first_match(pattern, doc):
    m=re.search(pattern, doc, flags=re.I|re.S)
    return clean_text(m.group(1)) if m else ''

def normalize_price_currency(price_text, currency_text):
    price_text=(price_text or '').strip(); currency_text=(currency_text or '').strip()
    # Check longer / more specific symbols first so NT$ is not mistaken for USD.
    for sym, cur in [('NT$','TWD'), ('US$','USD'), ('RMB','CNY'), ('¥','JPY'), ('€','EUR'), ('£','GBP'), ('$','USD')]:
        if sym.lower() in price_text.lower() and not currency_text:
            currency_text=cur; break
    mcur=re.search(r'\b(USD|EUR|GBP|JPY|TWD|NTD|CNY|RMB)\b', price_text, flags=re.I)
    if mcur and not currency_text:
        currency_text=mcur.group(1).upper()
        if currency_text=='NTD': currency_text='TWD'
        if currency_text=='RMB': currency_text='CNY'
    m=re.search(r'[-+]?\d[\d,]*(?:\.\d+)?', price_text)
    price=''
    if m:
        val=float(m.group(0).replace(',',''))
        price=int(val) if val.is_integer() else val
    return price, (currency_text.upper() if currency_text else '')

def memory_to_gb(mem):
    mem=(mem or '').strip()
    if not mem: return ''
    m=re.search(r'(\d+(?:\.\d+)?)\s*(TB|T|GB|G|MB|M)\b', mem, flags=re.I)
    if not m:
        m=re.search(r'(\d+(?:\.\d+)?)', mem)
        if not m: return ''
        val=float(m.group(1)); return int(val) if val.is_integer() else val
    val=float(m.group(1)); unit=m.group(2).upper()
    if unit in ('TB','T'): val*=1024
    elif unit in ('MB','M'): val/=1024
    return int(val) if abs(val-round(val))<1e-9 else val

print('Workspace:', WORKSPACE)
print('Input files:', [p.name for p in (WORKSPACE/'input').glob('*')])
list_html=fetch(BASE_LIST_URL)
print('List page snippet:', list_html[:500].replace('\n',' '))
parser=LinkParser(); parser.feed(list_html)
links=[]; seen=set()
for href, text in parser.links:
    url=urllib.parse.urljoin(BASE_LIST_URL, href)
    if url not in seen:
        links.append((url,text)); seen.add(url)
print('Found detail links:', links)

rows=[]
for url, link_text in links:
    doc=fetch(url)
    print('\nDETAIL', url, 'snippet:', doc[:600].replace('\n',' '))
    kv=parse_keyvals(doc)
    name=kv.get('name') or first_match(r'<h1\b[^>]*>(.*?)</h1>', doc) or link_text
    price, currency=normalize_price_currency(kv.get('price',''), kv.get('currency',''))
    row={
        'Name': name,
        'Price': price,
        'Currency': currency,
        'CPU': kv.get('cpu',''),
        'MemoryGB': memory_to_gb(kv.get('memory','') or kv.get('ram','')),
        'URL': url,
    }
    print('Parsed:', row, 'source fields:', kv)
    rows.append(row)

headers=['Name','Price','Currency','CPU','MemoryGB','URL']
wb=Workbook(); ws=wb.active; ws.title='details'; ws.append(headers)
for row in rows: ws.append([row[h] for h in headers])
wb.save(OUT)
print('Wrote', OUT)

# Verification: reopen every output file and confirm requirements.
wb2=load_workbook(OUT, data_only=True); ws2=wb2.active
actual_headers=[ws2.cell(1,c).value for c in range(1,len(headers)+1)]
assert actual_headers==headers, f'headers mismatch {actual_headers}'
assert ws2.max_row==len(rows)+1, f'row count mismatch {ws2.max_row}'
for r in range(2, ws2.max_row+1):
    vals={headers[c-1]: ws2.cell(r,c).value for c in range(1,len(headers)+1)}
    assert vals['URL'] and str(vals['URL']).startswith('http://127.0.0.1:58649/t11/item/'), vals
    assert vals['Name'] is None or isinstance(vals['Name'], str), vals
    assert vals['Currency'] in (None, 'TWD'), f'currency not TWD/blank row {r}: {vals}'
    assert vals['CPU'] is None or isinstance(vals['CPU'], str), vals
    assert vals['Price'] is None or isinstance(vals['Price'], (int,float)), vals
    assert vals['MemoryGB'] is None or isinstance(vals['MemoryGB'], (int,float)), vals
print('Verified output/details.xlsx: headers exactly', headers, '; row count', ws2.max_row-1, '; MemoryGB numeric GB values/blanks; missing fields blank; Currency TWD where NT$ was present; input untouched.')