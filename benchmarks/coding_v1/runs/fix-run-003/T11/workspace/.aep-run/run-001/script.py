import re
import json
from html.parser import HTMLParser
from urllib.parse import urljoin
from urllib.request import urlopen, Request
from pathlib import Path
from openpyxl import Workbook

BASE_URL = 'http://127.0.0.1:51979/t11/list'
OUT = Path('output')
OUT.mkdir(exist_ok=True)


def fetch(url):
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(req, timeout=10) as r:
        charset = r.headers.get_content_charset() or 'utf-8'
        return r.read().decode(charset, errors='replace')

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            d = dict(attrs)
            href = d.get('href')
            if href:
                self.links.append(href)

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.current_href = None
    def handle_starttag(self, tag, attrs):
        if tag.lower() in ('br','p','div','li','tr','th','td','h1','h2','h3','dt','dd','span'):
            self.parts.append('\n')
    def handle_endtag(self, tag):
        if tag.lower() in ('p','div','li','tr','th','td','h1','h2','h3','dt','dd'):
            self.parts.append('\n')
    def handle_data(self, data):
        if data and data.strip():
            self.parts.append(data.strip())
    def text(self):
        txt = ' '.join(self.parts)
        txt = re.sub(r'\s*\n\s*', '\n', txt)
        txt = re.sub(r'[ \t\r\f\v]+', ' ', txt)
        txt = re.sub(r'\n+', '\n', txt)
        return txt.strip()


def clean_html_text(html):
    p = TextParser()
    p.feed(html)
    return p.text()


def get_meta(html, prop_names):
    for name in prop_names:
        # property/name="..." content="..." in either order
        m = re.search(r'<meta[^>]+(?:property|name)=["\']'+re.escape(name)+r'["\'][^>]+content=["\']([^"\']*)["\']', html, re.I)
        if m:
            return m.group(1).strip()
        m = re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']'+re.escape(name)+r'["\']', html, re.I)
        if m:
            return m.group(1).strip()
    return ''


def labels_from_text(text):
    result = {}
    # Capture common label/value patterns, including labels on adjacent lines.
    labels = ['Name', 'Price', 'Currency', 'CPU', 'Memory', 'MemoryGB']
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for i, ln in enumerate(lines):
        # Label: value or Label value
        for lab in labels:
            m = re.match(r'^' + re.escape(lab) + r'\s*[:：=-]\s*(.+)$', ln, re.I)
            if m and lab.lower() not in result:
                result[lab.lower()] = m.group(1).strip()
            elif re.fullmatch(re.escape(lab), ln, re.I) and i+1 < len(lines) and lab.lower() not in result:
                result[lab.lower()] = lines[i+1].strip()
    flat = '\n'.join(lines)
    for lab in labels:
        if lab.lower() in result:
            continue
        m = re.search(r'\b' + re.escape(lab) + r'\b\s*[:：=-]\s*([^\n]+)', flat, re.I)
        if m:
            result[lab.lower()] = m.group(1).strip()
    return result


def parse_json_ld(html):
    objs = []
    for m in re.finditer(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', html, re.I|re.S):
        raw = m.group(1).strip()
        try:
            data = json.loads(raw)
        except Exception:
            continue
        if isinstance(data, list): objs.extend(data)
        else: objs.append(data)
    return objs


def normalize_memory_gb(val):
    if val is None:
        return ''
    s = str(val).strip()
    if not s:
        return ''
    # Direct numeric
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(TB|T|GB|G|MB|M)?\b', s, re.I)
    if not m:
        return s
    num = float(m.group(1))
    unit = (m.group(2) or 'GB').upper()
    if unit in ('TB','T'):
        gb = num * 1024
    elif unit in ('MB','M'):
        gb = num / 1024
    else:
        gb = num
    if abs(gb - round(gb)) < 1e-9:
        return int(round(gb))
    return gb


def split_price_currency(price_val, currency_val=''):
    p = str(price_val or '').strip()
    c = str(currency_val or '').strip()
    # currency symbols/codes
    symbol_map = {'$':'USD', '€':'EUR', '£':'GBP', '¥':'JPY', 'NT$':'TWD'}
    if not c:
        cm = re.search(r'\b(USD|EUR|GBP|JPY|TWD|CNY|NTD)\b', p, re.I)
        if cm:
            c = cm.group(1).upper()
        elif 'NT$' in p:
            c = 'TWD'
        else:
            for sym, code in symbol_map.items():
                if sym in p:
                    c = code
                    break
    nm = re.search(r'([0-9][0-9,]*(?:\.[0-9]+)?)', p)
    price = nm.group(1).replace(',', '') if nm else p
    return price, c


def parse_detail(url, html):
    text = clean_html_text(html)
    labels = labels_from_text(text)
    row = {'Name':'', 'Price':'', 'Currency':'', 'CPU':'', 'MemoryGB':'', 'URL':url}

    # JSON-LD/Product if present
    for obj in parse_json_ld(html):
        candidates = []
        if isinstance(obj, dict):
            candidates.append(obj)
            if '@graph' in obj and isinstance(obj['@graph'], list):
                candidates.extend([x for x in obj['@graph'] if isinstance(x, dict)])
        for d in candidates:
            typ = d.get('@type')
            if typ and (typ == 'Product' or (isinstance(typ, list) and 'Product' in typ)):
                row['Name'] = row['Name'] or str(d.get('name','')).strip()
                offers = d.get('offers') or {}
                if isinstance(offers, list): offers = offers[0] if offers else {}
                if isinstance(offers, dict):
                    row['Price'] = row['Price'] or str(offers.get('price','')).strip()
                    row['Currency'] = row['Currency'] or str(offers.get('priceCurrency','')).strip()
                for prop in d.get('additionalProperty', []) if isinstance(d.get('additionalProperty'), list) else []:
                    if isinstance(prop, dict):
                        n = str(prop.get('name','')).lower()
                        v = prop.get('value','')
                        if n == 'cpu': row['CPU'] = row['CPU'] or str(v).strip()
                        if 'memory' in n: row['MemoryGB'] = row['MemoryGB'] or normalize_memory_gb(v)

    # meta/title fallback
    row['Name'] = row['Name'] or labels.get('name','') or get_meta(html, ['og:title', 'twitter:title'])
    if not row['Name']:
        m = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.I|re.S)
        if m:
            row['Name'] = clean_html_text(m.group(1))
        else:
            m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I|re.S)
            if m: row['Name'] = clean_html_text(m.group(1))

    price_raw = row['Price'] or labels.get('price','')
    row['Currency'] = row['Currency'] or labels.get('currency','')
    row['Price'], row['Currency'] = split_price_currency(price_raw, row['Currency'])

    row['CPU'] = row['CPU'] or labels.get('cpu','')
    mem_raw = row['MemoryGB'] or labels.get('memorygb','') or labels.get('memory','')
    row['MemoryGB'] = normalize_memory_gb(mem_raw)

    # Strip accidental labels/tails
    for k in ('Name','Price','Currency','CPU'):
        if isinstance(row[k], str):
            row[k] = re.sub(r'\s+', ' ', row[k]).strip()
    return row, text

# Fetch list and find detail links
list_html = fetch(BASE_URL)
parser = LinkParser(); parser.feed(list_html)
links = []
for href in parser.links:
    absu = urljoin(BASE_URL, href)
    if absu == BASE_URL:
        continue
    # Prefer t11 detail-ish internal links; keep all local t11 links if no explicit detail word.
    if '127.0.0.1:51979' in absu and '/t11/' in absu:
        links.append(absu)
# de-dupe preserve order
seen = set(); detail_urls=[]
for u in links:
    if u not in seen:
        seen.add(u); detail_urls.append(u)

# If many nav links, filter for product/detail identifiers if available.
preferred = [u for u in detail_urls if re.search(r'/(detail|product|item|p)/|[?&](id|sku)=', u, re.I)]
if preferred:
    detail_urls = preferred

print('List links found:', len(detail_urls))
for u in detail_urls:
    print('DETAIL', u)

rows=[]
for u in detail_urls:
    html = fetch(u)
    row, text = parse_detail(u, html)
    print('ROW', row)
    rows.append(row)

wb = Workbook()
ws = wb.active
ws.title = 'details'
headers = ['Name','Price','Currency','CPU','MemoryGB','URL']
ws.append(headers)
for r in rows:
    ws.append([r.get(h,'') for h in headers])
for col in ws.columns:
    max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
    ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 10), 60)
outfile = OUT / 'details.xlsx'
wb.save(outfile)
print('Saved', outfile.resolve(), 'rows', len(rows))
