from pathlib import Path
import csv
import json
from decimal import Decimal, InvalidOperation

WORKSPACE = Path('.')
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(parents=True, exist_ok=True)
OUTFILE = OUTPUT / 'reports.json'

FIELD_ORDER = ['device_id', 'test_name', 'status', 'value', 'unit']
STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}

def normalize_status(v):
    if v is None:
        return None
    key = str(v).strip().upper()
    return STATUS_MAP.get(key, str(v).strip())

def normalize_text(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s != '' else None

def normalize_value(v):
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    s = str(v).strip()
    if s == '':
        return None
    # Keep numeric values as JSON numbers where possible.
    try:
        d = Decimal(s)
        if d == d.to_integral_value():
            return int(d)
        return float(d)
    except (InvalidOperation, ValueError):
        return s

def make_record(device, test, status, value=None, unit=None):
    return {
        'device_id': '' if device is None else str(device).strip(),
        'test_name': '' if test is None else str(test).strip(),
        'status': normalize_status(status),
        'value': normalize_value(value),
        'unit': normalize_text(unit),
    }

def read_csv(path):
    rows = []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(make_record(
                row.get('DUT'),
                row.get('Item'),
                row.get('Result'),
                row.get('Measurement'),
                row.get('Unit'),
            ))
    return rows

def read_json(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data, dict):
        # Support a wrapped list if present, otherwise a single result object.
        for key in ('reports', 'results', 'data', 'items'):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    if not isinstance(data, list):
        raise ValueError(f'Unsupported JSON top-level in {path}: {type(data).__name__}')
    rows = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f'Unsupported JSON item in {path}: {item!r}')
        rows.append(make_record(
            item.get('device', item.get('device_id')),
            item.get('test', item.get('test_name')),
            item.get('outcome', item.get('status')),
            item.get('value'),
            item.get('unit'),
        ))
    return rows

def split_md_row(line):
    s = line.strip()
    if not (s.startswith('|') and s.endswith('|')):
        return None
    return [cell.strip() for cell in s.strip('|').split('|')]

def is_separator(cells):
    return all(cell and set(cell.replace(':', '').replace('-', '')) == set() for cell in cells)

def read_markdown(path):
    rows = []
    table_rows = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        cells = split_md_row(line)
        if cells is not None:
            table_rows.append(cells)
    if len(table_rows) < 2:
        return rows
    headers = table_rows[0]
    data_rows = table_rows[1:]
    if data_rows and is_separator(data_rows[0]):
        data_rows = data_rows[1:]
    for cells in data_rows:
        row = {headers[i]: cells[i] if i < len(cells) else None for i in range(len(headers))}
        rows.append(make_record(
            row.get('Device'),
            row.get('Test'),
            row.get('Status'),
            row.get('Value'),
            row.get('Unit'),
        ))
    return rows

reports = []
for path in sorted(INPUT.iterdir()):
    suffix = path.suffix.lower()
    if suffix == '.csv':
        reports.extend(read_csv(path))
    elif suffix == '.json':
        reports.extend(read_json(path))
    elif suffix in ('.md', '.markdown'):
        reports.extend(read_markdown(path))

with OUTFILE.open('w', encoding='utf-8') as f:
    json.dump(reports, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Reopen and verify every stated requirement.
loaded = json.loads(OUTFILE.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'reports.json must contain a JSON array'
assert len(loaded) == 6, f'expected 6 preserved records, got {len(loaded)}'
for i, rec in enumerate(loaded, 1):
    assert list(rec.keys()) == FIELD_ORDER, f'record {i} fields/order mismatch: {rec.keys()}'
    assert isinstance(rec['device_id'], str), f'record {i} device_id is not text'
    assert rec['status'] in ('Pass', 'Fail'), f'record {i} status not normalized: {rec["status"]!r}'
    assert rec['unit'] is None or isinstance(rec['unit'], str), f'record {i} unit is not string/null'
assert loaded[0]['device_id'] == 'D001' and loaded[0]['value'] == 12.5 and loaded[0]['unit'] == 'dBm'
assert loaded[1]['device_id'] == 'D002' and loaded[1]['value'] is None and loaded[1]['unit'] == 'dBm'
assert loaded[2]['device_id'] == 'D003' and loaded[2]['status'] == 'Pass' and loaded[2]['value'] == -35.2 and loaded[2]['unit'] == 'dB'
assert loaded[3]['device_id'] == 'D004' and loaded[3]['status'] == 'Fail' and loaded[3]['value'] == -20.1 and loaded[3]['unit'] is None
assert loaded[4]['device_id'] == 'D005' and loaded[4]['value'] == -90 and loaded[4]['unit'] == 'dBm'
assert loaded[5]['device_id'] == 'D006' and loaded[5]['value'] == -70 and loaded[5]['unit'] == 'dBm'
print('Wrote:', OUTFILE)
print('Verified: JSON array, 6 records preserved, exact fields/order, device_id text, statuses Pass/Fail, missing/blank value or missing unit as null.')
print(json.dumps(loaded, ensure_ascii=False, indent=2))
