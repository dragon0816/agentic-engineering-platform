from pathlib import Path
import csv, json

INPUT = Path('input')
OUTPUT = Path('output')
OUTPUT.mkdir(exist_ok=True)
OUTFILE = OUTPUT / 'reports.json'

STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}

def norm_status(s):
    key = '' if s is None else str(s).strip().upper()
    return STATUS_MAP.get(key, str(s).strip() if s is not None else None)

def norm_text(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s != '' else None

def norm_value(v):
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    s = str(v).strip()
    if s == '':
        return None
    try:
        f = float(s)
        if f.is_integer() and '.' not in s and 'e' not in s.lower():
            return int(f)
        return f
    except ValueError:
        return s

records = []

# CSV: DUT,Item,Result,Measurement,Unit
csv_path = INPUT / 'report_a.csv'
with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        records.append({
            'device_id': str(row.get('DUT', '')).strip(),
            'test_name': norm_text(row.get('Item')),
            'status': norm_status(row.get('Result')),
            'value': norm_value(row.get('Measurement')),
            'unit': norm_text(row.get('Unit')),
        })

# JSON: device,test,outcome,value,unit
json_path = INPUT / 'report_b.json'
with json_path.open('r', encoding='utf-8-sig') as f:
    data = json.load(f)
for row in data:
    records.append({
        'device_id': str(row.get('device', '')).strip(),
        'test_name': norm_text(row.get('test')),
        'status': norm_status(row.get('outcome')),
        'value': norm_value(row.get('value')) if 'value' in row else None,
        'unit': norm_text(row.get('unit')) if 'unit' in row else None,
    })

# Markdown table: | Device | Test | Status | Value | Unit |
md_path = INPUT / 'report_c.md'
lines = md_path.read_text(encoding='utf-8-sig').splitlines()
md_rows = []
for line in lines:
    stripped = line.strip()
    if not stripped.startswith('|') or not stripped.endswith('|'):
        continue
    cells = [c.strip() for c in stripped.strip('|').split('|')]
    # Skip separator rows like ---
    if all(set(c.replace(':','')) <= {'-'} and c.replace(':','') for c in cells):
        continue
    md_rows.append(cells)
if md_rows:
    headers = md_rows[0]
    for cells in md_rows[1:]:
        row = dict(zip(headers, cells))
        records.append({
            'device_id': str(row.get('Device', '')).strip(),
            'test_name': norm_text(row.get('Test')),
            'status': norm_status(row.get('Status')),
            'value': norm_value(row.get('Value')),
            'unit': norm_text(row.get('Unit')),
        })

with OUTFILE.open('w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)

# Reopen and verify all stated requirements.
loaded = json.loads(OUTFILE.read_text(encoding='utf-8'))
expected_keys = ['device_id', 'test_name', 'status', 'value', 'unit']
assert isinstance(loaded, list), 'Output must be a JSON array'
assert len(loaded) == 6, f'Expected 6 records, got {len(loaded)}'
for i, rec in enumerate(loaded, 1):
    assert list(rec.keys()) == expected_keys, f'Record {i} keys/order mismatch: {list(rec.keys())}'
    assert isinstance(rec['device_id'], str), f'Record {i} device_id is not text'
    assert rec['status'] in ('Pass', 'Fail'), f'Record {i} status not normalized: {rec["status"]}'
    assert 'value' in rec and 'unit' in rec, f'Record {i} missing value/unit field'

# Specific missing/null checks and preservation checks
by_id = {rec['device_id']: rec for rec in loaded}
assert set(by_id) == {'D001','D002','D003','D004','D005','D006'}, f'Unexpected IDs: {set(by_id)}'
assert by_id['D002']['value'] is None, 'Missing CSV Measurement should be null'
assert by_id['D004']['unit'] is None, 'Missing JSON unit should be null'
assert by_id['D001']['status'] == 'Pass'
assert by_id['D002']['status'] == 'Fail'
assert by_id['D003']['status'] == 'Pass'
assert by_id['D004']['status'] == 'Fail'
assert by_id['D005']['status'] == 'Pass'
assert by_id['D006']['status'] == 'Fail'
assert isinstance(by_id['D005']['value'], (int, float)) and by_id['D005']['value'] == -90

print(f'Wrote {OUTFILE}')
print('Verified: reports.json exists, is a JSON array, has 6 records, exact columns device_id/test_name/status/value/unit, device_id values are strings, statuses normalized, missing value/unit are null, and all source result IDs are preserved.')
print(OUTFILE.read_text(encoding='utf-8'))
