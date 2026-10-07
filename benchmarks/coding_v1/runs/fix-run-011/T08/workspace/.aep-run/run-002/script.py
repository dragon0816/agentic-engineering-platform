from pathlib import Path
import csv, json, re

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
output_path = output_dir / 'reports.json'

FIELDS = ['device_id', 'test_name', 'status', 'value', 'unit']
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

def normalize_text(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s != '' else None

def normalize_value(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        if s == '':
            return None
        # Return numeric values as numbers where possible, preserving non-numeric as text if ever present.
        try:
            if re.fullmatch(r'[+-]?\d+', s):
                return int(s)
            return float(s)
        except ValueError:
            return s
    return v

def make_record(device, test, status, value=None, unit=None):
    return {
        'device_id': '' if device is None else str(device).strip(),
        'test_name': normalize_text(test),
        'status': normalize_status(status),
        'value': normalize_value(value),
        'unit': normalize_text(unit),
    }

def parse_csv(path):
    out = []
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            out.append(make_record(
                row.get('DUT'),
                row.get('Item'),
                row.get('Result'),
                row.get('Measurement'),
                row.get('Unit'),
            ))
    return out

def parse_json(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data, dict):
        # Accept a wrapped list if present; otherwise one record.
        if 'records' in data and isinstance(data['records'], list):
            items = data['records']
        elif 'results' in data and isinstance(data['results'], list):
            items = data['results']
        else:
            items = [data]
    elif isinstance(data, list):
        items = data
    else:
        raise ValueError(f'Unsupported JSON root in {path.name}: {type(data).__name__}')
    out = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError(f'Unsupported JSON item in {path.name}: {item!r}')
        out.append(make_record(
            item.get('device', item.get('device_id')),
            item.get('test', item.get('test_name')),
            item.get('outcome', item.get('status')),
            item.get('value'),
            item.get('unit'),
        ))
    return out

def split_md_row(line):
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]
    return [cell.strip() for cell in line.split('|')]

def is_separator_row(cells):
    return all(re.fullmatch(r':?-{3,}:?', c.strip()) for c in cells if c.strip())

def parse_md(path):
    lines = [line for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip().startswith('|')]
    rows = [split_md_row(line) for line in lines]
    if not rows:
        return []
    header = rows[0]
    out = []
    for cells in rows[1:]:
        if is_separator_row(cells):
            continue
        row = dict(zip(header, cells))
        out.append(make_record(
            row.get('Device'),
            row.get('Test'),
            row.get('Status'),
            row.get('Value'),
            row.get('Unit'),
        ))
    return out

reports = []
for path in sorted(input_dir.iterdir()):
    suffix = path.suffix.lower()
    if suffix == '.csv':
        parsed = parse_csv(path)
    elif suffix == '.json':
        parsed = parse_json(path)
    elif suffix in ('.md', '.markdown'):
        parsed = parse_md(path)
    else:
        continue
    print(f'{path.name}: parsed {len(parsed)} records')
    reports.extend(parsed)

output_path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'wrote {output_path} with {len(reports)} records')

# Verification from saved output.
saved = json.loads(output_path.read_text(encoding='utf-8'))
assert isinstance(saved, list), 'reports.json must be a JSON list'
expected_count = 6
assert len(saved) == expected_count, f'expected {expected_count} records, got {len(saved)}'
for i, rec in enumerate(saved, 1):
    assert list(rec.keys()) == FIELDS, f'record {i} fields/order mismatch: {list(rec.keys())}'
    assert isinstance(rec['device_id'], str), f'record {i} device_id is not text'
    assert rec['status'] in ('Pass', 'Fail'), f'record {i} status not normalized: {rec["status"]!r}'
    assert 'value' in rec and 'unit' in rec, f'record {i} missing value/unit keys'
# Specific null checks from source missing data.
by_id = {rec['device_id']: rec for rec in saved}
assert by_id['D002']['value'] is None, 'D002 empty Measurement should be null'
assert by_id['D002']['unit'] == 'dBm', 'D002 unit should be retained'
assert by_id['D004']['unit'] is None, 'D004 missing unit should be null'
assert [rec['device_id'] for rec in saved] == ['D001', 'D002', 'D003', 'D004', 'D005', 'D006'], 'all records/order not preserved as expected'
print('verification passed: reports.json exists, has 6 records, exact fields, text device_id, normalized statuses, and required nulls')
print(output_path.read_text(encoding='utf-8'))