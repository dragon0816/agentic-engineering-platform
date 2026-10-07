from pathlib import Path
import re
from openpyxl import Workbook, load_workbook

ws = Path.cwd()
input_path = ws / 'input' / 'specs.md'
out_dir = ws / 'output'
out_dir.mkdir(exist_ok=True)
out_path = out_dir / 'specs.xlsx'

text = input_path.read_text(encoding='utf-8')

# Split into product sections by markdown H2 headings. Only parse explicitly written bullet fields.
sections = re.split(r'(?m)^##\s+', text)
product_sections = []
for sec in sections[1:]:
    title, _, body = sec.partition('\n')
    if title.strip():
        product_sections.append((title.strip(), body))

headers = ['Model', 'FrequencyMinMHz', 'FrequencyMaxMHz', 'BandwidthMHz', 'Interface']
rows = []

def to_mhz(value_text: str):
    """Convert a numeric value with MHz/GHz unit to MHz. Return None if not explicit."""
    m = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(GHz|MHz)\b', value_text, flags=re.I)
    if not m:
        return None
    val = float(m.group(1))
    unit = m.group(2).lower()
    if unit == 'ghz':
        val *= 1000.0
    return val

def clean_number(n):
    if n is None:
        return None
    if abs(n - round(n)) < 1e-9:
        return int(round(n))
    return n

for title, body in product_sections:
    fields = {}
    for line in body.splitlines():
        m = re.match(r'^\s*-\s*([^:]+):\s*(.*?)\s*$', line)
        if m:
            fields[m.group(1).strip().lower()] = m.group(2).strip()

    model = fields.get('model', '')

    freq_min = freq_max = ''
    freq_text = fields.get('frequency')
    if freq_text:
        # Require an explicitly written range and unit. If the first bound lacks a unit,
        # use the unit written after the second bound because it applies to the explicit range.
        fm = re.search(r'([0-9]+(?:\.[0-9]+)?)\s*(GHz|MHz)?\s*[–—-]\s*([0-9]+(?:\.[0-9]+)?)\s*(GHz|MHz)\b', freq_text, flags=re.I)
        if fm:
            unit1 = fm.group(2) or fm.group(4)
            unit2 = fm.group(4)
            v1 = float(fm.group(1))
            v2 = float(fm.group(3))
            if unit1.lower() == 'ghz':
                v1 *= 1000.0
            if unit2.lower() == 'ghz':
                v2 *= 1000.0
            freq_min = clean_number(v1)
            freq_max = clean_number(v2)

    bandwidth = ''
    bw_text = fields.get('bandwidth')
    if bw_text:
        mhz = to_mhz(bw_text)
        if mhz is not None:
            bandwidth = clean_number(mhz)

    interface = ''
    int_text = fields.get('interface')
    if int_text:
        # Treat slash/comma separated explicit interfaces as multiple interfaces.
        parts = [p.strip() for p in re.split(r'\s*(?:/|,|;)\s*', int_text) if p.strip()]
        interface = ';'.join(parts)

    rows.append([model, freq_min, freq_max, bandwidth, interface])

wb = Workbook()
wsheet = wb.active
wsheet.title = 'specs'
wsheet.append(headers)
for row in rows:
    wsheet.append(row)
wb.save(out_path)

# Verification: reopen output and confirm stated requirements.
wb2 = load_workbook(out_path, data_only=True)
sh = wb2['specs']
read_headers = [cell.value for cell in sh[1]]
read_rows = [list(r) for r in sh.iter_rows(min_row=2, values_only=True)]

print('created:', out_path)
print('sheet:', sh.title)
print('headers:', read_headers)
print('row_count:', len(read_rows))
for r in read_rows:
    print(r)

assert read_headers == headers, f'Unexpected headers: {read_headers}'
assert len(read_rows) == 3, f'Expected 3 product rows, got {len(read_rows)}'
expected = [
    ['RX-100', 2400, 2500, 80, 'USB;LAN'],
    ['RX-200', 900, 930, 20, 'LAN'],
    ['RX-300', 5000, 6000, None, 'USB'],
]
assert read_rows == expected, f'Rows differ. Expected {expected}, got {read_rows}'
for row in read_rows:
    assert isinstance(row[0], str) and row[0].startswith('RX-')
    assert isinstance(row[1], (int, float)) and isinstance(row[2], (int, float))
    assert row[3] is None or isinstance(row[3], (int, float))
    assert row[4] is None or isinstance(row[4], str)
print('verification: PASS - specs.xlsx reopened; headers, 3 product rows, MHz conversions, semicolon interfaces, and blank missing Bandwidth were confirmed.')