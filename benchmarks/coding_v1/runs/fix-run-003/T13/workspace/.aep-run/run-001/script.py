import json, re, time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from html.parser import HTMLParser
from html import unescape
from openpyxl import Workbook

WORKSPACE = Path.cwd()
OUT = WORKSPACE / 'output'
OUT.mkdir(parents=True, exist_ok=True)
LIST_URL = 'http://127.0.0.1:51979/t13/list'

class AnchorParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.anchors = []
        self._in_a = False
        self._href = None
        self._texts = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            self._in_a = True
            self._href = dict(attrs).get('href')
            self._texts = []
    def handle_data(self, data):
        if self._in_a:
            self._texts.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self._in_a:
            text = ' '.join(' '.join(self._texts).split())
            self.anchors.append((self._href, text))
            self._in_a = False
            self._href = None
            self._texts = []

class TextParser(HTMLParser):
    block_tags = {'p','div','li','tr','td','th','br','h1','h2','h3','h4','section','article','span'}
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.title_parts = []
        self.in_title = False
        self.attrs_seen = []
    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        ad = {k.lower(): (v or '') for k, v in attrs}
        self.attrs_seen.append((t, ad))
        if t == 'title':
            self.in_title = True
        if t in self.block_tags:
            self.parts.append('\n')
        # keep useful attribute values; many benchmark pages store values in data-* or aria-label
        useful = []
        for k, v in ad.items():
            if k in ('content','value') or k.startswith('data-') or k in ('aria-label','title'):
                if v and any(word in (k + ' ' + v).lower() for word in ['price','currency','cpu','processor','name']):
                    useful.append(v)
        if useful:
            self.parts.append(' '.join(useful))
    def handle_endtag(self, tag):
        t = tag.lower()
        if t == 'title':
            self.in_title = False
        if t in self.block_tags:
            self.parts.append('\n')
    def handle_data(self, data):
        if data and data.strip():
            self.parts.append(data.strip())
            if self.in_title:
                self.title_parts.append(data.strip())


def fetch(url, attempts=1, retry_500=False):
    last_exc = None
    for i in range(attempts):
        try:
            req = Request(url, headers={'User-Agent': 'Agent benchmark scraper/1.0'})
            with urlopen(req, timeout=10) as resp:
                charset = resp.headers.get_content_charset() or 'utf-8'
                return resp.read().decode(charset, errors='replace'), resp.getcode(), None, i + 1
        except HTTPError as e:
            last_exc = e
            if retry_500 and e.code == 500 and i < attempts - 1:
                time.sleep(0.15)
                continue
            try:
                body = e.read().decode('utf-8', errors='replace')
            except Exception:
                body = ''
            return body, e.code, e, i + 1
        except URLError as e:
            last_exc = e
            if i < attempts - 1:
                time.sleep(0.15)
                continue
            return '', None, e, i + 1
    return '', None, last_exc, attempts


def clean_text_from_html(html):
    html = re.sub(r'<(script|style)\b.*?</\1>', ' ', html, flags=re.I|re.S)
    p = TextParser()
    p.feed(html)
    text = unescape(' '.join(p.parts))
    text = re.sub(r'[ \t\r\f\v]+', ' ', text)
    text = re.sub(r' *\n+ *', '\n', text)
    text = re.sub(r'\n{2,}', '\n', text).strip()
    title = ' '.join(p.title_parts).strip()
    return text, title


def strip_label(value):
    value = re.sub(r'^\s*(name|product\s*name|title|price|cpu|processor|currency)\s*[:\-–—]\s*', '', value, flags=re.I)
    return ' '.join(value.split()) if value else 'N/A'


def find_labeled(text, labels):
    # Work line-by-line first to avoid swallowing following fields.
    for line in text.split('\n'):
        line = line.strip(' -–—\t')
        for lab in labels:
            m = re.match(rf'^{re.escape(lab)}\s*[:\-–—]\s*(.+)$', line, flags=re.I)
            if m and m.group(1).strip():
                return strip_label(m.group(1).strip())
    # Inline fallback.
    pat = r'(?:' + '|'.join(re.escape(l) for l in labels) + r')\s*[:\-–—]\s*([^\n|;,]+)'
    m = re.search(pat, text, flags=re.I)
    return strip_label(m.group(1)) if m else 'N/A'


def parse_price_currency(text):
    currency = find_labeled(text, ['Currency'])
    if currency != 'N/A':
        currency = currency.upper()
    price = 'N/A'

    labeled_price = find_labeled(text, ['Price'])
    if labeled_price != 'N/A':
        # Try currency code plus amount or symbol plus amount in the labeled value.
        m = re.search(r'\b(USD|EUR|GBP|TWD|NTD|JPY|CNY|RMB|AUD|CAD)\b\s*\$?\s*([0-9][0-9,]*(?:\.\d+)?)', labeled_price, flags=re.I)
        if m:
            currency = m.group(1).upper()
            price = m.group(2).replace(',', '')
        else:
            m = re.search(r'([$€£¥]|NT\$)\s*([0-9][0-9,]*(?:\.\d+)?)', labeled_price, flags=re.I)
            if m:
                sym = m.group(1).upper()
                currency = {'$':'USD','€':'EUR','£':'GBP','¥':'JPY','NT$':'TWD'}.get(sym, currency)
                price = m.group(2).replace(',', '')
            else:
                m = re.search(r'([0-9][0-9,]*(?:\.\d+)?)\s*\b(USD|EUR|GBP|TWD|NTD|JPY|CNY|RMB|AUD|CAD)\b', labeled_price, flags=re.I)
                if m:
                    price = m.group(1).replace(',', '')
                    currency = m.group(2).upper()
                else:
                    m = re.search(r'[0-9][0-9,]*(?:\.\d+)?', labeled_price)
                    if m:
                        price = m.group(0).replace(',', '')
    if price == 'N/A':
        # Global fallback, preferring explicit price context.
        for pat in [
            r'Price\s*[:\-–—]?\s*\b(USD|EUR|GBP|TWD|NTD|JPY|CNY|RMB|AUD|CAD)\b\s*\$?\s*([0-9][0-9,]*(?:\.\d+)?)',
            r'Price\s*[:\-–—]?\s*([$€£¥]|NT\$)\s*([0-9][0-9,]*(?:\.\d+)?)',
            r'([$€£¥]|NT\$)\s*([0-9][0-9,]*(?:\.\d+)?)',
            r'\b(USD|EUR|GBP|TWD|NTD|JPY|CNY|RMB|AUD|CAD)\b\s*\$?\s*([0-9][0-9,]*(?:\.\d+)?)',
        ]:
            m = re.search(pat, text, flags=re.I)
            if not m:
                continue
            if len(m.groups()) >= 2:
                g1, g2 = m.group(1), m.group(2)
                if re.match(r'[0-9]', g1):
                    price = g1.replace(',', '')
                    currency = g2.upper()
                elif re.match(r'[0-9]', g2):
                    price = g2.replace(',', '')
                    if g1 in ('$','€','£','¥') or g1.upper() == 'NT$':
                        currency = {'$':'USD','€':'EUR','£':'GBP','¥':'JPY','NT$':'TWD'}.get(g1.upper(), currency)
                    else:
                        currency = g1.upper()
                break
    if currency == 'NTD':
        currency = 'TWD'
    if currency == 'RMB':
        currency = 'CNY'
    return price or 'N/A', currency or 'N/A'


def parse_name(text, title, fallback):
    name = find_labeled(text, ['Name', 'Product Name', 'Title'])
    if name != 'N/A':
        return name
    # first heading-ish non-label line
    for line in text.split('\n'):
        line = ' '.join(line.split())
        if not line:
            continue
        if re.match(r'^(price|currency|cpu|processor|specifications?|details?)\b', line, flags=re.I):
            continue
        if len(line) <= 120:
            return line
    if title:
        return title
    return fallback or 'N/A'


def parse_cpu(text):
    cpu = find_labeled(text, ['CPU', 'Processor'])
    if cpu != 'N/A':
        return cpu
    m = re.search(r'\b((?:Intel|AMD|Apple|Qualcomm|MediaTek|NVIDIA)[^\n;,|]{2,80})', text, flags=re.I)
    return ' '.join(m.group(1).split()) if m else 'N/A'

# Fetch list and collect first five product links.
list_html, list_code, list_err, _ = fetch(LIST_URL)
if list_err is not None or not list_html:
    raise SystemExit(f'Could not fetch product list {LIST_URL}: {list_err or list_code}')

ap = AnchorParser()
ap.feed(list_html)
products = []
seen = set()
for href, text in ap.anchors:
    if not href:
        continue
    url = urljoin(LIST_URL, href)
    if url in seen or url.rstrip('/') == LIST_URL.rstrip('/'):
        continue
    # Avoid navigation/login links; keep likely product links. If all links are products this is harmless.
    low = (href + ' ' + text).lower()
    if any(bad in low for bad in ['#', 'javascript:', 'mailto:', 'cart', 'home']) and 'product' not in low and 'detail' not in low:
        continue
    seen.add(url)
    products.append({'Name': text or 'N/A', 'URL': url})
    if len(products) == 5:
        break

if len(products) < 5:
    # Fallback: include any unique anchors not already selected.
    for href, text in ap.anchors:
        if not href:
            continue
        url = urljoin(LIST_URL, href)
        if url in seen or url.rstrip('/') == LIST_URL.rstrip('/'):
            continue
        seen.add(url)
        products.append({'Name': text or 'N/A', 'URL': url})
        if len(products) == 5:
            break

rows = []
warnings = []
for p in products[:5]:
    url = p['URL']
    html, code, err, attempts = fetch(url, attempts=3, retry_500=True)
    if err is not None or code is None or code >= 400:
        rows.append({
            'Name': p['Name'] or 'N/A',
            'Price': 'N/A',
            'Currency': 'N/A',
            'CPU': 'N/A',
            'URL': url,
            'FetchStatus': 'error',
        })
        warnings.append({'url': url, 'name': p['Name'] or 'N/A', 'status': 'error', 'http_status': code, 'attempts': attempts})
        continue
    text, title = clean_text_from_html(html)
    name = parse_name(text, title, p['Name'])
    price, currency = parse_price_currency(text)
    cpu = parse_cpu(text)
    rows.append({
        'Name': name or p['Name'] or 'N/A',
        'Price': price or 'N/A',
        'Currency': currency or 'N/A',
        'CPU': cpu or 'N/A',
        'URL': url,
        'FetchStatus': 'ok',
    })
    warnings.append({'url': url, 'name': name or p['Name'] or 'N/A', 'status': 'ok', 'http_status': code, 'attempts': attempts})

# Ensure exactly five output rows if list parsing was unexpectedly short.
while len(rows) < 5:
    rows.append({'Name': 'N/A', 'Price': 'N/A', 'Currency': 'N/A', 'CPU': 'N/A', 'URL': 'N/A', 'FetchStatus': 'error'})
    warnings.append({'url': 'N/A', 'name': 'N/A', 'status': 'error', 'http_status': None, 'attempts': 0, 'message': 'fewer than five products found'})

wb = Workbook()
ws = wb.active
ws.title = 'Products'
headers = ['Name', 'Price', 'Currency', 'CPU', 'URL', 'FetchStatus']
ws.append(headers)
for r in rows[:5]:
    ws.append([r.get(h, 'N/A') if r.get(h, 'N/A') not in (None, '') else 'N/A' for h in headers])
for col in ws.columns:
    max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col)
    ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 2, 12), 80)
wb.save(OUT / 'robust_products.xlsx')

with (OUT / 'warnings.json').open('w', encoding='utf-8') as f:
    json.dump(warnings[:5], f, ensure_ascii=False, indent=2)

print('Fetched list status:', list_code)
print('Products found:', len(products))
print(json.dumps(rows[:5], ensure_ascii=False, indent=2))
print('Wrote', OUT / 'robust_products.xlsx')
print('Wrote', OUT / 'warnings.json')
