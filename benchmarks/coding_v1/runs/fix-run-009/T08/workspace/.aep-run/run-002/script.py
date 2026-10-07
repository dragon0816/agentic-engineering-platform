from pathlib import Path
import csv, json, re

WORKSPACE = Path.cwd()
INPUT = WORKSPACE / 'input'
OUTPUT = WORKSPACE / 'output'
OUTPUT.mkdir(parents=True, exist_ok=True)
OUTFILE = OUTPUT / 'reports.json'

STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}
TARGET_FIELDS = ['device_id', 'test_name', 'status', 'value', 'unit']


def normalize_status(s):
    if s is None:
        return None
    key = str(s).strip().upper()
    return STATUS_MAP.get(key, str(s).strip())


def null_if_missing(v):
    if v is None:
        return None
    if isinstance(v, str):
        stripped = v.strip()
        return stripped if stripped != '' else None
    return v


def make_record(device_id=None, test_name=None, status=None, value=None, unit=None):
    return {
        'device_id': None if device_id is None else str(device_id).strip(),
        'test_name': None if test_name is None else str(test_name).strip(),
        'status': normalize_status(status),
        'value': null_if_missing(value),
        'unit': null_if_missing(unit),
    }


def parse_csv(path):
    records = []
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append(make_record(
                device_id=row.get('device_id') or row.get('Device') or row.get('DUT') or row.get('device') or row.get('ID'),
                test_name=row.get('test_name') or row.get('Test') or row.get('Item') or row.get('test'),
                status=row.get('status') or row.get('Status') or row.get('Result') or row.get('outcome'),
                value=row.get('value') or row.get('Value') or row.get('Measurement'),
                unit=row.get('unit') or row.get('Unit'),
            ))
    return records


def records_from_json_obj(obj):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for key in ('reports', 'results', 'data', 'items'):
            if isinstance(obj.get(key), list):
                return obj[key]
        return [obj]
    raise ValueError('Unsupported JSON top-level type')


def parse_json_file(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    records = []
    for item in records_from_json_obj(data):
        if not isinstance(item, dict):
            raise ValueError(f'JSON record is not an object: {item!r}')
        records.append(make_record(
            device_id=item.get('device_id') or item.get('Device') or item.get('DUT') or item.get('device') or item.get('ID'),
            test_name=item.get('test_name') or item.get('Test') or item.get('Item') or item.get('test'),
            status=item.get('status') or item.get('Status') or item.get('Result') or item.get('outcome'),
            value=item.get('value') if 'value' in item else (item.get('Value') if 'Value' in item else item.get('Measurement')),
            unit=item.get('unit') if 'unit' in item else item.get('Unit'),
        ))
    return records


def split_md_row(line):
    line = line.strip()
    if not (line.startswith('|') and line.endswith('|')):
        return None
    return [cell.strip() for cell in line.strip('|').split('|')]


def is_separator_row(cells):
    return all(re.fullmatch(r':?-{3,}:?', cell.strip()) for cell in cells)


def parse_markdown(path):
    rows = []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        cells = split_md_row(line)
        if cells is not None:
            rows.append(cells)
    if not rows:
        return []
    header = rows[0]
    body = rows[1:]
    if body and is_separator_row(body[0]):
        body = body[1:]
    records = []
    for cells in body:
        row = {header[i]: cells[i] if i < len(cells) else '' for i in range(len(header))}
        records.append(make_record(
            device_id=row.get('device_id') or row.get('Device') or row.get('DUT') or row.get('device') or row.get('ID'),
            test_name=row.get('test_name') or row.get('Test') or row.get('Item') or row.get('test'),
            status=row.get('status') or row.get('Status') or row.get('Result') or row.get('outcome'),
            value=row.get('value') or row.get('Value') or row.get('Measurement'),
            unit=row.get('unit') or row.get('Unit'),
        ))
    return records


all_records = []
source_counts = {}
for path in sorted(INPUT.iterdir()):
    suffix = path.suffix.lower()
    if suffix == '.csv':
        recs = parse_csv(path)
    elif suffix == '.json':
        recs = parse_json_file(path)
    elif suffix in ('.md', '.markdown'):
        recs = parse_markdown(path)
    else:
        continue
    source_counts[path.name] = len(recs)
    all_records.extend(recs)

with OUTFILE.open('w', encoding='utf-8') as f:
    json.dump(all_records, f, ensure_ascii=False, indent=2)
    f.write('\n')

print('WROTE', OUTFILE)
print('Source counts:', source_counts)
print('Total records:', len(all_records))
print('Output sample:', json.dumps(all_records[:3], ensure_ascii=False, indent=2))

# Verification: reopen output file and confirm stated requirements.
loaded = json.loads(OUTFILE.read_text(encoding='utf-8'))
errors = []
if not isinstance(loaded, list):
    errors.append('reports.json is not a JSON array')
expected_total = sum(source_counts.values())
if len(loaded) != expected_total:
    errors.append(f'row count mismatch: {len(loaded)} != {expected_total}')
for i, rec in enumerate(loaded, 1):
    if list(rec.keys()) != TARGET_FIELDS:
        errors.append(f'record {i} fields/order mismatch: {list(rec.keys())}')
    if rec.get('status') not in ('Pass', 'Fail'):
        errors.append(f'record {i} status not normalized: {rec.get("status")!r}')
    if rec.get('device_id') is not None and not isinstance(rec.get('device_id'), str):
        errors.append(f'record {i} device_id is not text: {type(rec.get("device_id")).__name__}')
    if 'value' not in rec or 'unit' not in rec:
        errors.append(f'record {i} missing value or unit key')
# Confirm at least one missing JSON unit became null, per inspected input.
if not any(rec['device_id'] == 'D004' and rec['unit'] is None for rec in loaded):
    errors.append('D004 missing unit was not preserved as null')
if errors:
    print('VERIFY FAILED:')
    for e in errors:
        print('-', e)
    raise SystemExit(1)
print('VERIFY OK: reports.json is a list; row count matches all input records; fields are exactly', TARGET_FIELDS, '; statuses normalized; device_id values are strings; missing value/unit represented as null.')
