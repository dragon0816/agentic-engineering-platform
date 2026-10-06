from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from html.parser import HTMLParser
import json, re, time, os, sys
from openpyxl import Workbook, load_workbook

WORKSPACE = Path.cwd()
OUT = WORKSPACE / 'output'
OUT.mkdir(parents=True, exist_ok=True)
LIST_URL = 'http://127.0.0.1:56996/t13/list'
HEADERS = {'User-Agent': 'Mozilla/5.0'}

print('WORKSPACE', WORKSPACE)
print('INPUT FILES:')
for p in sorted((WORKSPACE / 'input').glob('**/*')):
    print('-', p.relative_to(WORKSPACE), 'file' if p.is_file() else 'dir')

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self._href = None
        self._text = []
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            self._href = dict(attrs).get('href')
            self._text = []
    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)
    def handle_endtag(self, tag):
        if tag.lower() == 'a' and self._href is not None:
            text = ' '.join(''.join(self._text).split())
            self.links.append((text, self._href))
            self._href = None
            self._text = []

class DetailParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
        self.rows = []
        self._current_cell = None
        self._current_row = None
        self._tag_stack = []
        self.by_tag = {'h1': [], 'h2': [], 'title': []}
        self._capture_tag = None
        self._capture_text = []
    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        self._tag_stack.append(tag)
        if tag == 'tr':
            self._current_row = []
        elif tag in ('td', 'th'):
            self._current_cell = []
        if tag in self.by_tag:
            self._capture_tag = tag
            self._capture_text = []
    def handle_data(self, data):
        s = data.strip()
        if s:
            self.texts.append(s)
            if self._current_cell is not None:
                self._current_cell.append(s)
            if self._capture_tag is not None:
                self._capture_text.append(s)
    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in ('td', 'th') and self._current_cell is not None:
            if self._current_row is not None:
                self._current_row.append(' '.join(' '.join(self._current_cell).split()))
            self._current_cell = None
        elif tag == 'tr' and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None
        if tag == self._capture_tag:
            val = ' '.join(' '.join(self._capture_text).split())
            if val:
                self.by_tag[tag].append(val)
            self._capture_tag = None
            self._capture_text = []
        if self._tag_stack:
            try:
                idx = len(self._tag_stack) - 1 - self._tag_stack[::-1].index(tag)
                self._tag_stack.pop(idx)
            except ValueError:
                pass

def fetch_url(url, max_500_attempts=1):
    attempts = 0
    last_error = None
    while True:
        attempts += 1
        try:
            req = Request(url, headers=HEADERS)
            with urlopen(req, timeout=10) as r:
                raw = r.read()
                charset = r.headers.get_content_charset() or 'utf-8'
                return {'ok': True, 'status_code': getattr(r, 'status', 200), 'text': raw.decode(charset, errors='replace'), 'attempts': attempts, 'error': None}
        except HTTPError as e:
            status = getattr(e, 'code', None)
            last_error = f'HTTP {status}'
            # Requirement: detail page HTTP 500 at most 3 attempts.
            if status == 500 and attempts < max_500_attempts:
                continue
            return {'ok': False, 'status_code': status, 'text': '', 'attempts': attempts, 'error': last_error}
        except Exception as e:
            last_error = f'{type(e).__name__}: {e}'
            return {'ok': False, 'status_code': None, 'text': '', 'attempts': attempts, 'error': last_error}

def clean(v):
    if v is None:
        return 'N/A'
    v = ' '.join(str(v).strip().split())
    return v if v else 'N/A'

def find_labeled_value(texts, labels):
    # Handles strings like "CPU: A16", "Price - 199 USD" or adjacent tokens "CPU", "A16".
    for i, t in enumerate(texts):
        tt = ' '.join(t.split())
        for label in labels:
            m = re.match(rf'^{re.escape(label)}\s*[:：\-]\s*(.+)$', tt, flags=re.I)
            if m and m.group(1).strip():
                return m.group(1).strip()
            if re.fullmatch(rf'{re.escape(label)}', tt, flags=re.I) and i + 1 < len(texts):
                nxt = texts[i + 1].strip()
                if nxt:
                    return nxt
    return None

def parse_price_currency(texts):
    joined = ' | '.join(texts)
    price_label = find_labeled_value(texts, ['Price', '價格'])
    candidates = [price_label] if price_label else []
    candidates.append(joined)
    currency_words = '(USD|EUR|TWD|NTD|JPY|CNY|GBP|AUD|CAD|RMB|US\$|NT\$|\$|€|£|¥)'
    for c in candidates:
        if not c:
            continue
        patterns = [
            rf'(?P<cur>{currency_words})\s*(?P<price>[0-9][0-9,]*(?:\.[0-9]+)?)',
            rf'(?P<price>[0-9][0-9,]*(?:\.[0-9]+)?)\s*(?P<cur>{currency_words})',
        ]
        for pat in patterns:
            m = re.search(pat, c, flags=re.I)
            if m:
                price = m.group('price').replace(',', '')
                cur = m.group('cur')
                symbol_map = {'$': 'USD', 'US$': 'USD', 'NT$': 'TWD', '€': 'EUR', '£': 'GBP', '¥': 'JPY'}
                cur_norm = symbol_map.get(cur.upper() if cur.upper() in symbol_map else cur, cur.upper())
                if cur in symbol_map:
                    cur_norm = symbol_map[cur]
                return price, cur_norm
    # If there is an explicit Price value but no currency, keep price only.
    if price_label:
        m = re.search(r'[0-9][0-9,]*(?:\.[0-9]+)?', price_label)
        if m:
            return m.group(0).replace(',', ''), 'N/A'
    return 'N/A', 'N/A'

def parse_detail(html, fallback_name):
    p = DetailParser()
    p.feed(html)
    texts = [' '.join(t.split()) for t in p.texts if t.strip()]
    # Print a concise detail sample for traceability.
    name = None
    for tag in ('h1', 'h2', 'title'):
        if p.by_tag.get(tag):
            name = p.by_tag[tag][0]
            break
    if not name:
        name = fallback_name

    cpu = None
    # Prefer table rows with CPU label.
    for row in p.rows:
        if row and re.search(r'\bCPU\b|處理器', row[0], flags=re.I):
            if len(row) >= 2:
                cpu = row[1]
                break
            elif len(row) == 1:
                cpu = re.sub(r'(?i)^\s*(CPU|處理器)\s*[:：\-]?\s*', '', row[0]).strip() or None
                break
    if not cpu:
        cpu = find_labeled_value(texts, ['CPU', 'Processor', '處理器'])

    price, currency = parse_price_currency(texts)
    return {
        'Name': clean(name),
        'Price': clean(price),
        'Currency': clean(currency),
        'CPU': clean(cpu),
    }, texts[:20], p.rows[:10]

# Fetch and parse list.
list_result = fetch_url(LIST_URL, max_500_attempts=1)
if not list_result['ok']:
    raise RuntimeError(f'Could not fetch product list: {list_result["error"]}')
print('\nLIST STATUS', list_result['status_code'])
print('LIST MARKUP SAMPLE')
print(list_result['text'][:1500])

lp = LinkParser()
lp.feed(list_result['text'])
products = []
seen = set()
for name, href in lp.links:
    if not href:
        continue
    abs_url = urljoin(LIST_URL, href)
    key = (name, abs_url)
    if key in seen:
        continue
    seen.add(key)
    products.append({'list_name': clean(name), 'url': abs_url})
products = products[:5]
print('LIST PRODUCTS', products)
if len(products) != 5:
    raise RuntimeError(f'Expected 5 products from list, found {len(products)}')

rows = []
warnings = []
for idx, prod in enumerate(products, 1):
    detail = fetch_url(prod['url'], max_500_attempts=3)
    if detail['ok']:
        parsed, sample_texts, sample_rows = parse_detail(detail['text'], prod['list_name'])
        row = {
            'Name': parsed['Name'],
            'Price': parsed['Price'],
            'Currency': parsed['Currency'],
            'CPU': parsed['CPU'],
            'URL': prod['url'],
            'FetchStatus': 'ok',
        }
        missing = [k for k in ('Price', 'Currency', 'CPU') if row[k] == 'N/A']
        warnings.append({
            'Name': row['Name'],
            'URL': prod['url'],
            'FetchStatus': 'ok',
            'Attempts': detail['attempts'],
            'Warnings': [f'missing {m}' for m in missing],
        })
        print(f'\nDETAIL {idx} OK {prod["url"]} attempts={detail["attempts"]}')
        print('texts sample:', sample_texts)
        print('rows sample:', sample_rows)
    else:
        row = {
            'Name': prod['list_name'],
            'Price': 'N/A',
            'Currency': 'N/A',
            'CPU': 'N/A',
            'URL': prod['url'],
            'FetchStatus': 'error',
        }
        warnings.append({
            'Name': prod['list_name'],
            'URL': prod['url'],
            'FetchStatus': 'error',
            'Attempts': detail['attempts'],
            'Warnings': [detail['error'] or 'fetch failed'],
        })
        print(f'\nDETAIL {idx} ERROR {prod["url"]} attempts={detail["attempts"]} error={detail["error"]}')
    rows.append(row)

# Write workbook.
columns = ['Name', 'Price', 'Currency', 'CPU', 'URL', 'FetchStatus']
wb = Workbook()
ws = wb.active
ws.title = 'Products'
ws.append(columns)
for row in rows:
    ws.append([row[c] for c in columns])
for col in range(1, len(columns) + 1):
    ws.column_dimensions[chr(64 + col)].width = 24
xlsx_path = OUT / 'robust_products.xlsx'
wb.save(xlsx_path)

warnings_path = OUT / 'warnings.json'
with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)

# Verification: reopen outputs and check stated requirements from saved files.
print('\nVERIFY OUTPUTS')
wb2 = load_workbook(xlsx_path, data_only=True)
ws2 = wb2.active
headers = [cell.value for cell in ws2[1]]
print('xlsx headers:', headers)
assert headers == columns, f'headers mismatch: {headers}'
saved_rows = []
for r in ws2.iter_rows(min_row=2, values_only=True):
    if all(v is None for v in r):
        continue
    saved_rows.append(dict(zip(columns, r)))
print('xlsx row_count:', len(saved_rows))
assert len(saved_rows) == 5, f'row count mismatch: {len(saved_rows)}'
for i, r in enumerate(saved_rows, 1):
    for c in columns:
        assert r[c] is not None and str(r[c]) != '', f'row {i} column {c} blank'
    assert r['FetchStatus'] in ('ok', 'error'), f'row {i} invalid FetchStatus'
    if r['FetchStatus'] == 'error':
        assert r['Price'] == 'N/A' and r['Currency'] == 'N/A' and r['CPU'] == 'N/A', f'row {i} error row unknown fields not N/A'
    assert isinstance(r['Name'], str) and isinstance(r['URL'], str), f'row {i} name/url not text'
    assert str(r['URL']).startswith('http://127.0.0.1:56996/'), f'row {i} URL unexpected'

with warnings_path.open('r', encoding='utf-8') as f:
    saved_warnings = json.load(f)
print('warnings entries:', len(saved_warnings))
assert isinstance(saved_warnings, list) and len(saved_warnings) == 5
for i, w in enumerate(saved_warnings, 1):
    assert w.get('FetchStatus') in ('ok', 'error'), f'warning {i} bad status'
    if w.get('FetchStatus') == 'ok':
        assert w.get('FetchStatus') == 'ok'
    if w.get('FetchStatus') == 'error':
        assert int(w.get('Attempts', 0)) <= 3, f'warning {i} attempts > 3'

print('WROTE', xlsx_path)
print('WROTE', warnings_path)
print('SAVED ROWS:')
for r in saved_rows:
    print(r)
print('Verification passed: robust_products.xlsx has exact requested columns, five rows, nonblank text Name/URL, N/A placeholders for unknown/error fields, valid FetchStatus values; warnings.json has five entries and error retry attempts are <= 3.')
