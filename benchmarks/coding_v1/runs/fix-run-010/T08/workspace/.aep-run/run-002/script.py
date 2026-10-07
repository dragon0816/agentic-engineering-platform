from pathlib import Path
import csv, json

base = Path.cwd()
input_dir = base / 'input'
output_dir = base / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
out_path = output_dir / 'reports.json'

STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}
REQUIRED_KEYS = ['device_id', 'test_name', 'status', 'value', 'unit']


def normalize_status(value):
    if value is None:
        return None
    s = str(value).strip()
    return STATUS_MAP.get(s.upper(), s)


def normalize_value(value):
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        if v == '':
            return None
        try:
            # Keep integer-looking numbers as int, others as float.
            n = float(v)
            return int(n) if n.is_integer() and all(ch not in v.lower() for ch in ['.', 'e']) else n
        except ValueError:
            return v
    return value


def normalize_unit(value):
    if value is None:
        return None
    if isinstance(value, str):
        v = value.strip()
        return v if v != '' else None
    return str(value)


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
        for r in reader:
            rows.append(record(
                r.get('DUT'),
                r.get('Item'),
                r.get('Result'),
                r.get('Measurement'),
                r.get('Unit'),
            ))
    return rows


def parse_json_file(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data, dict):
        # Accept common container shapes while keeping all listed records.
        for key in ('reports', 'results', 'data', 'items'):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    rows = []
    for r in data:
        rows.append(record(
            r.get('device_id', r.get('device', r.get('DUT', r.get('Device')))),
            r.get('test_name', r.get('test', r.get('Item', r.get('Test')))),
            r.get('status', r.get('outcome', r.get('Result', r.get('Status')))),
            r.get('value', r.get('Measurement', r.get('Value'))),
            r.get('unit', r.get('Unit')),
        ))
    return rows


def split_md_row(line):
    line = line.strip()
    if line.startswith('|'):
        line = line[1:]
    if line.endswith('|'):
        line = line[:-1]
    return [cell.strip() for cell in line.split('|')]


def is_separator(cells):
    return all(cell and set(cell.replace(':', '').replace('-', '')) == set() for cell in cells)


def parse_markdown(path):
    lines = [ln for ln in path.read_text(encoding='utf-8-sig').splitlines() if ln.strip().startswith('|')]
    if not lines:
        return []
    header = split_md_row(lines[0])
    rows = []
    for ln in lines[1:]:
        cells = split_md_row(ln)
        if is_separator(cells):
            continue
        row = dict(zip(header, cells))
        rows.append(record(
            row.get('device_id', row.get('Device', row.get('DUT'))),
            row.get('test_name', row.get('Test', row.get('Item'))),
            row.get('status', row.get('Status', row.get('Result'))),
            row.get('value', row.get('Value', row.get('Measurement'))),
            row.get('unit', row.get('Unit')),
        ))
    return rows


reports = []
for path in sorted(input_dir.iterdir()):
    suffix = path.suffix.lower()
    if suffix == '.csv':
        parsed = parse_csv(path)
    elif suffix == '.json':
        parsed = parse_json_file(path)
    elif suffix in ('.md', '.markdown'):
        parsed = parse_markdown(path)
    else:
        continue
    print(f'parsed {path.name}: {len(parsed)} rows')
    reports.extend(parsed)

out_path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
print('wrote', out_path, 'rows=', len(reports))

# Verification: reopen saved output and confirm stated requirements.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
assert isinstance(loaded, list), 'reports.json must contain a JSON array'
assert len(loaded) == 6, f'expected all 6 input records, got {len(loaded)}'
for i, item in enumerate(loaded, start=1):
    assert list(item.keys()) == REQUIRED_KEYS, f'row {i} keys mismatch: {list(item.keys())}'
    assert isinstance(item['device_id'], str), f'row {i} device_id is not text'
    assert item['status'] in ('Pass', 'Fail'), f'row {i} status not normalized: {item["status"]}'
    assert item['unit'] is None or isinstance(item['unit'], str), f'row {i} unit invalid'
    assert item['value'] is None or isinstance(item['value'], (int, float, str)), f'row {i} value invalid'

# Specific null and mapping checks from observed input.
by_id = {item['device_id']: item for item in loaded}
assert by_id['D002']['value'] is None, 'blank CSV Measurement should be null'
assert by_id['D004']['unit'] is None, 'missing JSON unit should be null'
assert by_id['D001']['status'] == 'Pass'
assert by_id['D002']['status'] == 'Fail'
assert by_id['D003']['status'] == 'Pass'
assert by_id['D004']['status'] == 'Fail'
assert by_id['D005']['status'] == 'Pass'
assert by_id['D006']['status'] == 'Fail'
print('verification passed: reports.json exists, has required columns, 6 retained records, text IDs, normalized statuses, and nulls for missing value/unit')
print(json.dumps(loaded, ensure_ascii=False, indent=2))