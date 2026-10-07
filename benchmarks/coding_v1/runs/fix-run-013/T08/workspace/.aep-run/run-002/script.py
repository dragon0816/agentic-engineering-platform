from pathlib import Path
import csv, json, re

workspace = Path('.')
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

FIELD_ORDER = ['device_id', 'test_name', 'status', 'value', 'unit']
STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}

def norm_status(value):
    if value is None:
        return None
    key = str(value).strip().upper()
    return STATUS_MAP.get(key, str(value).strip())

def norm_optional(value):
    if value is None:
        return None
    s = str(value).strip()
    return None if s == '' else s

def norm_value(value):
    if value is None:
        return None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value
    s = str(value).strip()
    if s == '':
        return None
    # Convert numeric-looking values to numbers while preserving IDs as text separately.
    try:
        if re.fullmatch(r'[+-]?\d+', s):
            return int(s)
        if re.fullmatch(r'[+-]?(?:\d+\.\d*|\d*\.\d+)(?:[eE][+-]?\d+)?|[+-]?\d+[eE][+-]?\d+', s):
            return float(s)
    except Exception:
        pass
    return s

def make_record(device, test, status, value=None, unit=None):
    return {
        'device_id': '' if device is None else str(device).strip(),
        'test_name': '' if test is None else str(test).strip(),
        'status': norm_status(status),
        'value': norm_value(value),
        'unit': norm_optional(unit),
    }

records = []

# CSV: DUT, Item, Result, Measurement, Unit
csv_path = input_dir / 'report_a.csv'
with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    print('CSV headers:', reader.fieldnames)
    for row in reader:
        records.append(make_record(
            row.get('DUT'), row.get('Item'), row.get('Result'), row.get('Measurement'), row.get('Unit')
        ))

# JSON: list with device, test, outcome, value, unit (unit may be absent)
json_path = input_dir / 'report_b.json'
with json_path.open('r', encoding='utf-8-sig') as f:
    data = json.load(f)
print('JSON type:', type(data).__name__, 'records:', len(data) if isinstance(data, list) else 'n/a')
if isinstance(data, dict):
    # Allow common wrapper forms while keeping all listed records.
    for key in ('records', 'results', 'reports', 'data'):
        if isinstance(data.get(key), list):
            data = data[key]
            break
if not isinstance(data, list):
    raise ValueError('JSON input is not a list or supported wrapped list')
for row in data:
    records.append(make_record(
        row.get('device'), row.get('test'), row.get('outcome'), row.get('value'), row.get('unit')
    ))

# Markdown table: Device, Test, Status, Value, Unit
md_path = input_dir / 'report_c.md'
lines = [line.strip() for line in md_path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]
table_rows = []
for line in lines:
    if line.startswith('|') and line.endswith('|'):
        cells = [cell.strip() for cell in line.strip('|').split('|')]
        table_rows.append(cells)
print('Markdown table rows including header/separator:', len(table_rows))
if len(table_rows) < 2:
    raise ValueError('Markdown table not found')
headers = table_rows[0]
for cells in table_rows[1:]:
    # skip separator row like ---|---
    if all(re.fullmatch(r':?-{3,}:?', c or '') for c in cells):
        continue
    row = dict(zip(headers, cells))
    records.append(make_record(
        row.get('Device'), row.get('Test'), row.get('Status'), row.get('Value'), row.get('Unit')
    ))

# Ensure exactly the unified fields and order.
records = [{k: rec.get(k) for k in FIELD_ORDER} for rec in records]

out_path = output_dir / 'reports.json'
with out_path.open('w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
    f.write('\n')
print('Wrote', out_path, 'records:', len(records))
print(json.dumps(records, ensure_ascii=False, indent=2))

# Verification: reopen output and validate requirements.
with out_path.open('r', encoding='utf-8') as f:
    loaded = json.load(f)
assert isinstance(loaded, list), 'reports.json must contain a JSON array'
assert len(loaded) == 6, f'Expected 6 records, got {len(loaded)}'
for i, rec in enumerate(loaded, 1):
    assert list(rec.keys()) == FIELD_ORDER, f'Record {i} fields/order mismatch: {list(rec.keys())}'
    assert isinstance(rec['device_id'], str), f'Record {i} device_id is not text'
    assert rec['status'] in ('Pass', 'Fail'), f'Record {i} status not normalized: {rec["status"]!r}'
    assert rec['unit'] is None or isinstance(rec['unit'], str), f'Record {i} unit must be text or null'
    assert rec['value'] is None or isinstance(rec['value'], (int, float, str)), f'Record {i} bad value type'
# Specific missing checks from inputs.
assert loaded[1]['value'] is None, 'CSV blank Measurement should be null'
assert loaded[3]['unit'] is None, 'JSON missing unit should be null'
print('CHECK OK: output file exists; 6 records preserved; fields/order match; device_id is text; statuses normalized; missing/blank value or unit represented as null.')