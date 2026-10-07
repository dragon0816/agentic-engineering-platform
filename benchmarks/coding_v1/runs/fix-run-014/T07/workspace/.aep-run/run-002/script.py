from pathlib import Path
import re
from openpyxl import Workbook, load_workbook

ws = Path.cwd()
infile = ws / 'input' / 'specs.md'
outdir = ws / 'output'
outdir.mkdir(exist_ok=True)
outfile = outdir / 'specs.xlsx'

text = infile.read_text(encoding='utf-8')

headers = ['Model', 'FrequencyMinMHz', 'FrequencyMaxMHz', 'Bandwidth', 'Interface']
rows = []

# Split into product sections by level-2 headings.
sections = re.split(r'(?m)^##\s+', text)
for section in sections[1:]:
    lines = [ln.strip() for ln in section.splitlines() if ln.strip()]
    if not lines:
        continue
    kv = {}
    for ln in lines[1:]:  # skip heading title like P1
        m = re.match(r'^-\s*([^:]+):\s*(.*?)\s*$', ln)
        if m:
            kv[m.group(1).strip().lower()] = m.group(2).strip()
    if not kv:
        continue

    model = kv.get('model', '')
    fmin = ''
    fmax = ''
    freq = kv.get('frequency', '')
    if freq:
        # Require an explicit range and unit. Unit at end applies to both endpoints.
        fm = re.match(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*[–-]\s*([0-9]+(?:\.[0-9]+)?)\s*([GMK]?Hz)\s*$', freq, re.IGNORECASE)
        if fm:
            a, b, unit = fm.groups()
            factor = {'ghz': 1000, 'mhz': 1, 'khz': 0.001, 'hz': 0.000001}[unit.lower()]
            fmin = float(a) * factor
            fmax = float(b) * factor

    bandwidth = ''
    bw = kv.get('bandwidth', '')
    if bw:
        bm = re.match(r'^\s*([0-9]+(?:\.[0-9]+)?)\s*([GMK]?Hz)\s*$', bw, re.IGNORECASE)
        if bm:
            value, unit = bm.groups()
            factor = {'ghz': 1000, 'mhz': 1, 'khz': 0.001, 'hz': 0.000001}[unit.lower()]
            bandwidth = float(value) * factor

    interface = ''
    if 'interface' in kv:
        # Multiple interfaces are written with semicolons. Do not infer beyond listed tokens.
        interface = ';'.join(part.strip() for part in re.split(r'\s*/\s*', kv['interface']) if part.strip())

    rows.append([model, fmin, fmax, bandwidth, interface])

wb = Workbook()
sh = wb.active
sh.title = 'specs'
sh.append(headers)
for row in rows:
    sh.append(row)
wb.save(outfile)

# Verification: reopen output and confirm stated requirements.
wb2 = load_workbook(outfile, data_only=True)
sh2 = wb2['specs']
read_headers = [c.value for c in sh2[1]]
read_rows = [list(r) for r in sh2.iter_rows(min_row=2, values_only=True)]
print('created:', outfile)
print('headers:', read_headers)
print('row_count:', len(read_rows))
for r in read_rows:
    print('row:', r)

assert read_headers == headers, read_headers
assert len(read_rows) == 3, len(read_rows)
expected = [
    ['RX-100', 2400, 2500, 80, 'USB;LAN'],
    ['RX-200', 900, 930, 20, 'LAN'],
    ['RX-300', 5000, 6000, None, 'USB'],
]
for got, exp in zip(read_rows, expected):
    # openpyxl reads blank cells as None
    assert got[0] == exp[0]
    assert abs(got[1] - exp[1]) < 1e-9
    assert abs(got[2] - exp[2]) < 1e-9
    if exp[3] is None:
        assert got[3] is None
    else:
        assert abs(got[3] - exp[3]) < 1e-9
    assert got[4] == exp[4]
print('verification: specs.xlsx has required columns, 3 rows, MHz numeric frequency/bandwidth values, blank missing bandwidth, and semicolon-separated interfaces.')