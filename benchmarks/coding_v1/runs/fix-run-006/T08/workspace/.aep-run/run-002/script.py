from pathlib import Path
import csv, json, re

ws = Path.cwd()
input_dir = ws / 'input'
output_dir = ws / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}
FIELDS = ['device_id', 'test_name', 'status', 'value', 'unit']


def normalize_status(value):
    if value is None:
        return None
    key = str(value).strip().upper()
    return STATUS_MAP.get(key, str(value).strip())


def normalize_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        s = value.strip()
        if s == '':
            return None
        # Keep numbers as numeric values where possible; IDs are handled separately as text.
        try:
            if re.fullmatch(r'[+-]?\d+', s):
                return int(s)
            return float(s)
        except ValueError:
            return s
    return value


def normalize_unit(value):
    if value is None:
        return None
    s = str(value).strip()
    return s if s != '' else None


def record(device_id, test_name, status, value=None, unit=None):
    return {
        'device_id': '' if device_id is None else str(device_id).strip(),
        'test_name': '' if test_name is None else str(test_name).strip(),
        'status': normalize_status(status),
        'value': normalize_value(value),
        'unit': normalize_unit(unit),
    }


def parse_csv(path):
    rows = []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        print(f'CSV headers for {path.name}: {reader.fieldnames}')
        for row in reader:
            rows.append(record(
                row.get('DUT'),
                row.get('Item'),
                row.get('Result'),
                row.get('Measurement'),
                row.get('Unit'),
            ))
    return rows


def parse_json(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    print(f'JSON top-level for {path.name}: {type(data).__name__}, count={len(data) if isinstance(data, list) else "n/a"}')
    if isinstance(data, dict):
        # Accept either a single record or a list under a common container key.
        for key in ('results', 'reports', 'items', 'data'):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    rows = []
    for item in data:
        rows.append(record(
            item.get('device'),
            item.get('test'),
            item.get('outcome'),
            item.get('value'),
            item.get('unit'),
        ))
    return rows


def split_md_row(line):
    stripped = line.strip()
    if not (stripped.startswith('|') and stripped.endswith('|')):
        return None
    return [cell.strip() for cell in stripped.strip('|').split('|')]


def is_separator(cells):
    return all(re.fullmatch(r':?-{3,}:?', c.replace(' ', '')) for c in cells)


def parse_markdown(path):
    lines = path.read_text(encoding='utf-8-sig').splitlines()
    table_rows = [split_md_row(line) for line in lines]
    table_rows = [r for r in table_rows if r]
    print(f'Markdown table rows for {path.name}: {len(table_rows)} including header/separator')
    if not table_rows:
        return []
    headers = table_rows[0]
    data_rows = [r for r in table_rows[1:] if not is_separator(r)]
    index = {name.strip().lower(): i for i, name in enumerate(headers)}

    def get(row, name):
        i = index.get(name.lower())
        return row[i] if i is not None and i < len(row) else None

    rows = []
    for row in data_rows:
        rows.append(record(
            get(row, 'Device'),
            get(row, 'Test'),
            get(row, 'Status'),
            get(row, 'Value'),
            get(row, 'Unit'),
        ))
    return rows


all_records = []
for path in sorted(input_dir.iterdir()):
    suffix = path.suffix.lower()
    if suffix == '.csv':
        parsed = parse_csv(path)
    elif suffix == '.json':
        parsed = parse_json(path)
    elif suffix in ('.md', '.markdown'):
        parsed = parse_markdown(path)
    else:
        print(f'Skipping unsupported file: {path.name}')
        continue
    print(f'Parsed {len(parsed)} records from {path.name}')
    all_records.extend(parsed)

out_path = output_dir / 'reports.json'
out_path.write_text(json.dumps(all_records, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Wrote {out_path} with {len(all_records)} records')

# Verification: reopen output and confirm stated requirements.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'reports.json must be a JSON list'
assert len(loaded) == 6, f'expected 6 records, got {len(loaded)}'
for i, rec in enumerate(loaded, 1):
    assert list(rec.keys()) == FIELDS, f'record {i} fields/order mismatch: {list(rec.keys())}'
    assert isinstance(rec['device_id'], str), f'record {i} device_id is not text'
    assert rec['status'] in ('Pass', 'Fail'), f'record {i} status not normalized: {rec["status"]}'
    assert ('value' in rec and 'unit' in rec), f'record {i} missing value/unit keys'
    assert rec['value'] is None or isinstance(rec['value'], (int, float, str)), f'record {i} invalid value type'
    assert rec['unit'] is None or isinstance(rec['unit'], str), f'record {i} invalid unit type'

expected = [
    {'device_id':'D001','test_name':'TxPower','status':'Pass','value':12.5,'unit':'dBm'},
    {'device_id':'D002','test_name':'TxPower','status':'Fail','value':None,'unit':'dBm'},
    {'device_id':'D003','test_name':'EVM','status':'Pass','value':-35.2,'unit':'dB'},
    {'device_id':'D004','test_name':'EVM','status':'Fail','value':-20.1,'unit':None},
    {'device_id':'D005','test_name':'Sensitivity','status':'Pass','value':-90,'unit':'dBm'},
    {'device_id':'D006','test_name':'Sensitivity','status':'Fail','value':-70,'unit':'dBm'},
]
assert loaded == expected, 'output content did not match expected normalized records'
print('Verified reports.json: file name, 6 preserved records, unified field names/order, text IDs, normalized statuses, null missing/blank value or unit, and expected content.')
