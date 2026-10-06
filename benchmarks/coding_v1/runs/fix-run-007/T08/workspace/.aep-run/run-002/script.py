from pathlib import Path
import csv, json, re

workspace = Path('.')
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

def normalize_text_or_null(v):
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        return v if v != '' else None
    return v

def normalize_value(v):
    v = normalize_text_or_null(v)
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return v
    text = str(v).strip()
    # Preserve numeric values as JSON numbers when possible.
    try:
        if re.fullmatch(r'[+-]?\d+', text):
            return int(text)
        if re.fullmatch(r'[+-]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?', text):
            return float(text)
    except Exception:
        pass
    return text

def make_record(device, test, status, value=None, unit=None):
    return {
        'device_id': '' if device is None else str(device).strip(),
        'test_name': None if test is None else str(test).strip(),
        'status': normalize_status(status),
        'value': normalize_value(value),
        'unit': normalize_text_or_null(unit),
    }

def parse_csv(path):
    records = []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(make_record(
                row.get('DUT'),
                row.get('Item'),
                row.get('Result'),
                row.get('Measurement'),
                row.get('Unit'),
            ))
    return records

def parse_json(path):
    data = json.load(path.open('r', encoding='utf-8-sig'))
    if isinstance(data, dict):
        # Accept common wrappers while preserving every result.
        for key in ('reports', 'results', 'data', 'items'):
            if isinstance(data.get(key), list):
                data = data[key]
                break
        else:
            data = [data]
    if not isinstance(data, list):
        raise ValueError(f'Unsupported JSON top-level in {path}: {type(data).__name__}')
    records = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError(f'JSON item is not an object in {path}: {item!r}')
        records.append(make_record(
            item.get('device', item.get('device_id')),
            item.get('test', item.get('test_name')),
            item.get('outcome', item.get('status')),
            item.get('value') if 'value' in item else item.get('Measurement'),
            item.get('unit') if 'unit' in item else item.get('Unit'),
        ))
    return records

def split_md_row(line):
    line = line.strip()
    if not (line.startswith('|') and line.endswith('|')):
        return None
    return [cell.strip() for cell in line.strip('|').split('|')]

def is_separator(cells):
    return all(re.fullmatch(r':?-{3,}:?', c.strip()) for c in cells)

def parse_markdown(path):
    rows = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        cells = split_md_row(line)
        if cells is None:
            continue
        if is_separator(cells):
            continue
        rows.append(cells)
    if not rows:
        return []
    headers = [h.strip().lower() for h in rows[0]]
    records = []
    for cells in rows[1:]:
        # Pad short rows; ignore surplus cells after known headers.
        cells = cells + [''] * (len(headers) - len(cells))
        row = dict(zip(headers, cells))
        records.append(make_record(
            row.get('device') or row.get('device_id') or row.get('dut'),
            row.get('test') or row.get('test_name') or row.get('item'),
            row.get('status') or row.get('result') or row.get('outcome'),
            row.get('value') if 'value' in row else row.get('measurement'),
            row.get('unit'),
        ))
    return records

all_records = []
counts = {}
for path in sorted(input_dir.iterdir()):
    suffix = path.suffix.lower()
    if suffix == '.csv':
        recs = parse_csv(path)
    elif suffix == '.json':
        recs = parse_json(path)
    elif suffix in ('.md', '.markdown'):
        recs = parse_markdown(path)
    else:
        continue
    counts[path.name] = len(recs)
    all_records.extend(recs)

# Ensure exact field set/order on every record.
all_records = [{field: rec.get(field) for field in FIELDS} for rec in all_records]

with output_path.open('w', encoding='utf-8') as f:
    json.dump(all_records, f, ensure_ascii=False, indent=2)
    f.write('\n')

print('Wrote', output_path.as_posix())
print('Input record counts:', counts)
print('Total records:', len(all_records))
print('Preview:')
print(json.dumps(all_records, ensure_ascii=False, indent=2))

# Verification: reopen output and confirm stated requirements.
loaded = json.load(output_path.open('r', encoding='utf-8'))
errors = []
if not isinstance(loaded, list):
    errors.append('reports.json is not a JSON array')
expected_total = sum(counts.values())
if len(loaded) != expected_total:
    errors.append(f'row count {len(loaded)} != expected {expected_total}')
for i, rec in enumerate(loaded, 1):
    if list(rec.keys()) != FIELDS:
        errors.append(f'record {i} fields/order {list(rec.keys())} != {FIELDS}')
    if not isinstance(rec.get('device_id'), str):
        errors.append(f'record {i} device_id is not text: {rec.get("device_id")!r}')
    if rec.get('status') not in ('Pass', 'Fail'):
        errors.append(f'record {i} status not normalized to Pass/Fail: {rec.get("status")!r}')
    if 'value' not in rec or 'unit' not in rec:
        errors.append(f'record {i} missing value or unit key')
# Specific source-derived null checks.
if loaded[1]['value'] is not None:
    errors.append('CSV blank Measurement for D002 was not null')
if loaded[3]['unit'] is not None:
    errors.append('JSON missing unit for D004 was not null')
if errors:
    print('VERIFICATION FAILED')
    for e in errors:
        print('-', e)
    raise SystemExit(1)
print('VERIFICATION PASSED: reports.json reopened; exact fields/order, text IDs, normalized statuses, null placeholders, and row count confirmed.')