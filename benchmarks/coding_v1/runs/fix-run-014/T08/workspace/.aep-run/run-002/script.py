from pathlib import Path
import csv, json, re

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}

def normalize_status(s):
    if s is None:
        return None
    key = str(s).strip().upper()
    return STATUS_MAP.get(key, str(s).strip())

def normalize_value(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if s == '':
            return None
        # Preserve numeric values as JSON numbers when possible.
        try:
            if re.fullmatch(r'[+-]?\d+', s):
                return int(s)
            return float(s)
        except ValueError:
            return s
    return v

def normalize_unit(u):
    if u is None:
        return None
    if isinstance(u, str):
        s = u.strip()
        return s if s != '' else None
    return u

records = []

# CSV: DUT,Item,Result,Measurement,Unit
csv_path = input_dir / 'report_a.csv'
with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        records.append({
            'device_id': str(row.get('DUT', '')).strip(),
            'test_name': str(row.get('Item', '')).strip(),
            'status': normalize_status(row.get('Result')),
            'value': normalize_value(row.get('Measurement')),
            'unit': normalize_unit(row.get('Unit')),
        })

# JSON: device,test,outcome,value,unit
json_path = input_dir / 'report_b.json'
with json_path.open('r', encoding='utf-8') as f:
    data = json.load(f)
for row in data:
    records.append({
        'device_id': str(row.get('device', '')).strip(),
        'test_name': str(row.get('test', '')).strip(),
        'status': normalize_status(row.get('outcome')),
        'value': normalize_value(row.get('value')),
        'unit': normalize_unit(row.get('unit')),
    })

# Markdown pipe table: Device, Test, Status, Value, Unit
md_path = input_dir / 'report_c.md'
lines = [line.strip() for line in md_path.read_text(encoding='utf-8').splitlines() if line.strip()]
table_lines = [line for line in lines if line.startswith('|') and line.endswith('|')]
if table_lines:
    headers = [h.strip() for h in table_lines[0].strip('|').split('|')]
    for line in table_lines[2:]:  # skip header and separator
        cells = [c.strip() for c in line.strip('|').split('|')]
        row = dict(zip(headers, cells))
        records.append({
            'device_id': str(row.get('Device', '')).strip(),
            'test_name': str(row.get('Test', '')).strip(),
            'status': normalize_status(row.get('Status')),
            'value': normalize_value(row.get('Value')),
            'unit': normalize_unit(row.get('Unit')),
        })

out_path = output_dir / 'reports.json'
with out_path.open('w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
    f.write('\n')

print(f'wrote {out_path}')
print(f'record_count={len(records)}')
print(json.dumps(records, ensure_ascii=False, indent=2))

# Verification: reopen output and check every stated requirement.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
expected_fields = ['device_id', 'test_name', 'status', 'value', 'unit']
assert isinstance(loaded, list), 'reports.json must contain a JSON array'
assert len(loaded) == 6, f'expected 6 records, got {len(loaded)}'
for i, rec in enumerate(loaded, start=1):
    assert list(rec.keys()) == expected_fields, f'record {i} fields/order mismatch: {list(rec.keys())}'
    assert isinstance(rec['device_id'], str), f'record {i} device_id is not text'
    assert rec['status'] in ('Pass', 'Fail'), f'record {i} status not normalized: {rec["status"]}'
    assert 'value' in rec and 'unit' in rec, f'record {i} missing value/unit fields'
assert loaded[1]['value'] is None, 'missing CSV Measurement should be null'
assert loaded[3]['unit'] is None, 'missing JSON unit should be null'
assert loaded[0]['status'] == 'Pass'
assert loaded[1]['status'] == 'Fail'
assert loaded[2]['status'] == 'Pass'
assert loaded[3]['status'] == 'Fail'
print('verification passed: output file exists, JSON array has 6 records, unified fields are present, device_id values are strings, statuses normalized, missing value/unit are null.')