from pathlib import Path
from urllib.request import urlopen
from html.parser import HTMLParser
import csv, re, json, math

WORKSPACE = Path.cwd()
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(exist_ok=True)
OUTFILE = OUTPUT / 'merged_catalog.csv'

URLS = [
    'http://127.0.0.1:64493/t12/a',
    'http://127.0.0.1:64493/t12/b',
    'http://127.0.0.1:64493/t12/c',
]

class MiniHTML(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tokens = []
    def handle_starttag(self, tag, attrs):
        self.tokens.append(('start', tag, dict(attrs)))
    def handle_endtag(self, tag):
        self.tokens.append(('end', tag, {}))
    def handle_data(self, data):
        txt = data.strip()
        if txt:
            self.tokens.append(('data', None, txt))

def fetch(url):
    with urlopen(url, timeout=10) as r:
        return r.read().decode('utf-8', errors='replace')

def text_between(html, tag):
    return re.findall(fr'<{tag}[^>]*>(.*?)</{tag}>', html, flags=re.I|re.S)

def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s).strip()

def parse_price_currency(raw):
    raw = raw.strip()
    # Determine currency, preserving each source's currency as a normalized code.
    if 'NT$' in raw:
        currency = 'TWD'
    elif 'USD' in raw.upper():
        currency = 'USD'
    elif '€' in raw:
        currency = 'EUR'
    else:
        m = re.search(r'[A-Z]{3}', raw.upper())
        currency = m.group(0) if m else ''

    num = raw
    for marker in ['NT$', 'USD', '€']:
        num = num.replace(marker, '')
    num = num.strip()
    num = re.sub(r'[^0-9,\.\-]', '', num)

    # Convert according to separator style. If both separators exist, the last separator is decimal.
    if ',' in num and '.' in num:
        if num.rfind(',') > num.rfind('.'):
            # European: 1.299,00 -> 1299.00
            num = num.replace('.', '').replace(',', '.')
        else:
            # US: 1,250.00 -> 1250.00
            num = num.replace(',', '')
    elif ',' in num:
        # Single comma: thousands when exactly three trailing digits, otherwise decimal.
        parts = num.split(',')
        if len(parts[-1]) == 3 and all(p.isdigit() for p in parts):
            num = ''.join(parts)
        else:
            num = num.replace(',', '.')
    # else dot already decimal or no separator
    price = float(num)
    return price, currency

def parse_memory_gb(raw):
    raw = raw.strip()
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(GB|MB)', raw, flags=re.I)
    if not m:
        raise ValueError(f'Cannot parse memory: {raw!r}')
    value = float(m.group(1))
    unit = m.group(2).upper()
    gb = value if unit == 'GB' else value / 1024.0
    return gb

def fmt_num(x):
    # CSV-friendly numeric text; integers without .0, decimals preserved.
    if abs(x - round(x)) < 1e-9:
        return str(int(round(x)))
    return (f'{x:.10f}').rstrip('0').rstrip('.')

rows = []

# Source A: table with headers 型號/價格/記憶體.
url = URLS[0]
html = fetch(url)
trs = re.findall(r'<tr[^>]*>(.*?)</tr>', html, flags=re.I|re.S)
for tr in trs[1:]:
    cells = [strip_tags(x) for x in re.findall(r'<td[^>]*>(.*?)</td>', tr, flags=re.I|re.S)]
    if len(cells) >= 3:
        price, currency = parse_price_currency(cells[1])
        rows.append({
            'Model': cells[0],
            'Price': price,
            'Currency': currency,
            'MemoryGB': parse_memory_gb(cells[2]),
            'SourceURL': url,
        })

# Source B: repeated div.item.
url = URLS[1]
html = fetch(url)
items = re.findall(r'<div class="item"[^>]*>(.*?)</div>', html, flags=re.I|re.S)
for item in items:
    model = strip_tags(re.search(r'<h2[^>]*>(.*?)</h2>', item, flags=re.I|re.S).group(1))
    price_raw = strip_tags(re.search(r'<p class="price"[^>]*>(.*?)</p>', item, flags=re.I|re.S).group(1))
    mem_raw = strip_tags(re.search(r'<p class="mem"[^>]*>(.*?)</p>', item, flags=re.I|re.S).group(1))
    price, currency = parse_price_currency(price_raw)
    rows.append({
        'Model': model,
        'Price': price,
        'Currency': currency,
        'MemoryGB': parse_memory_gb(mem_raw),
        'SourceURL': url,
    })

# Source C: list items with data-model and text with em-dash separators.
url = URLS[2]
html = fetch(url)
lis = re.findall(r'<li[^>]*data-model="([^"]+)"[^>]*>(.*?)</li>', html, flags=re.I|re.S)
for model_attr, body in lis:
    text = strip_tags(body)
    parts = [p.strip() for p in text.split('—')]
    model = model_attr.strip() or parts[0]
    price_raw = parts[1]
    mem_raw = parts[2]
    price, currency = parse_price_currency(price_raw)
    rows.append({
        'Model': model,
        'Price': price,
        'Currency': currency,
        'MemoryGB': parse_memory_gb(mem_raw),
        'SourceURL': url,
    })

# Write output CSV with required columns, retaining same model rows from different sources.
fieldnames = ['Model', 'Price', 'Currency', 'MemoryGB', 'SourceURL']
with OUTFILE.open('w', newline='', encoding='utf-8-sig') as f:
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({
            'Model': row['Model'],
            'Price': fmt_num(row['Price']),
            'Currency': row['Currency'],
            'MemoryGB': fmt_num(row['MemoryGB']),
            'SourceURL': row['SourceURL'],
        })

# Verification: reopen output and confirm requirements.
with OUTFILE.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    out_rows = list(reader)

checks = []
checks.append(('file_exists', OUTFILE.exists()))
checks.append(('columns_exact', reader.fieldnames == fieldnames))
checks.append(('row_count_6', len(out_rows) == 6))
checks.append(('source_urls_all_present', sorted(set(r['SourceURL'] for r in out_rows)) == sorted(URLS)))
checks.append(('duplicate_model_NX1_retained', sum(1 for r in out_rows if r['Model'] == 'NX-1') == 2))
# Numeric parse checks: no currency symbols/thousands separators remain in Price, and values are parseable.
prices_ok = True
mem_ok = True
for r in out_rows:
    try:
        float(r['Price'])
        float(r['MemoryGB'])
    except Exception:
        prices_ok = False
    if any(sym in r['Price'] for sym in ['$', '€', ',', 'NT', 'USD']):
        prices_ok = False
checks.append(('price_numeric_no_currency_or_thousands', prices_ok))
expected = {
    ('NX-1', 'http://127.0.0.1:64493/t12/a'): ('12000', 'TWD', '16'),
    ('NX-2', 'http://127.0.0.1:64493/t12/a'): ('8500', 'TWD', '8'),
    ('NX-1', 'http://127.0.0.1:64493/t12/b'): ('399.5', 'USD', '16'),
    ('NX-3', 'http://127.0.0.1:64493/t12/b'): ('1250', 'USD', '32'),
    ('NX-4', 'http://127.0.0.1:64493/t12/c'): ('499', 'EUR', '4'),
    ('NX-5', 'http://127.0.0.1:64493/t12/c'): ('1299', 'EUR', '64'),
}
actual = {(r['Model'], r['SourceURL']): (r['Price'], r['Currency'], r['MemoryGB']) for r in out_rows}
checks.append(('values_match_expected', actual == expected))

print('WROTE', OUTFILE)
print('ROWS')
for r in out_rows:
    print(r)
print('CHECKS')
for name, ok in checks:
    print(name, ok)
if not all(ok for _, ok in checks):
    raise SystemExit('verification failed')
