from pathlib import Path
import csv, json, re

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

print('WORKSPACE:', workspace)
print('INPUT FILES:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)

print('\nINSPECTION:')
for p in sorted(input_dir.iterdir()):
    suffix = p.suffix.lower()
    print(f'\n## {p.name}')
    if suffix == '.csv':
        with p.open('r', encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            print('CSV headers:', reader.fieldnames)
            for i, row in zip(range(3), reader):
                print('CSV sample', i + 1, row)
    elif suffix == '.json':
        data = json.loads(p.read_text(encoding='utf-8-sig'))
        print('JSON top type:', type(data).__name__)
        sample = data[:3] if isinstance(data, list) else data
        print('JSON sample:', sample)
    elif suffix in ('.md', '.markdown'):
        text = p.read_text(encoding='utf-8-sig')
        print('Markdown first 1000 chars:')
        print(text[:1000])

TARGET_FIELDS = ['device_id', 'test_name', 'status', 'value', 'unit']
STATUS_MAP = {'OK': 'Pass', 'PASS': 'Pass', 'NG': 'Fail', 'FAIL': 'Fail'}
ALIASES = {
    'device_id': ['device_id', 'device id', 'deviceid', 'id', 'device', 'dut', 'dut_id'],
    'test_name': ['test_name', 'test name', 'testname', 'test', 'name', 'item'],
    'status': ['status', 'result', 'outcome', 'pass_fail', 'pass/fail'],
    'value': ['value', 'val', 'reading', 'measured', 'measurement', 'measurement_value'],
    'unit': ['unit', 'units', 'uom'],
}

def norm_key(k):
    return re.sub(r'[^a-z0-9]+', '_', str(k).strip().lower()).strip('_')

def clean_cell(v):
    if v is None:
        return None
    if isinstance(v, str):
        s = v.strip()
        return None if s == '' or s.lower() in {'null', 'none', 'nan', 'n/a', 'na'} else s
    return v

def find_value(row, target):
    normed = {norm_key(k): v for k, v in row.items()}
    for alias in ALIASES[target]:
        nk = norm_key(alias)
        if nk in normed:
            return clean_cell(normed[nk])
    return None

def normalize_status(v):
    v = clean_cell(v)
    if v is None:
        return None
    s = str(v).strip()
    return STATUS_MAP.get(s.upper(), s)

def normalize_record(row):
    rec = {
        'device_id': find_value(row, 'device_id'),
        'test_name': find_value(row, 'test_name'),
        'status': normalize_status(find_value(row, 'status')),
        'value': find_value(row, 'value'),
        'unit': find_value(row, 'unit'),
    }
    if rec['device_id'] is not None:
        rec['device_id'] = str(rec['device_id'])
    return rec

def flatten_json_records(obj):
    if isinstance(obj, list):
        out = []
        for item in obj:
            out.extend(flatten_json_records(item))
        return out
    if isinstance(obj, dict):
        row_keys = {norm_key(k) for k in obj.keys()}
        alias_keys = {norm_key(a) for aliases in ALIASES.values() for a in aliases}
        if row_keys & alias_keys:
            return [obj]
        out = []
        for v in obj.values():
            if isinstance(v, (list, dict)):
                out.extend(flatten_json_records(v))
        return out
    return []

def parse_markdown_tables(text):
    records = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if '|' not in lines[i]:
            i += 1
            continue
        block = []
        while i < len(lines) and '|' in lines[i]:
            block.append(lines[i].strip())
            i += 1
        if len(block) < 2:
            continue
        def split_md(row):
            row = row.strip()
            if row.startswith('|'):
                row = row[1:]
            if row.endswith('|'):
                row = row[:-1]
            return [c.strip() for c in row.split('|')]
        header = split_md(block[0])
        sep = split_md(block[1])
        if not all(re.fullmatch(r':?-{3,}:?', c.replace(' ', '')) for c in sep):
            continue
        for row_line in block[2:]:
            cells = split_md(row_line)
            cells += [''] * max(0, len(header) - len(cells))
            records.append(dict(zip(header, cells[:len(header)])))
    return records

all_records = []
source_counts = {}
source_rows = {}
for p in sorted(input_dir.iterdir()):
    suffix = p.suffix.lower()
    if suffix == '.csv':
        with p.open('r', encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
    elif suffix == '.json':
        rows = flatten_json_records(json.loads(p.read_text(encoding='utf-8-sig')))
    elif suffix in ('.md', '.markdown'):
        rows = parse_markdown_tables(p.read_text(encoding='utf-8-sig'))
    else:
        rows = []
    source_counts[p.name] = len(rows)
    source_rows[p.name] = rows
    all_records.extend(normalize_record(r) for r in rows)

out_path = output_dir / 'reports.json'
with out_path.open('w', encoding='utf-8') as f:
    json.dump(all_records, f, ensure_ascii=False, indent=2)

# Reopen and verify stated requirements and observed input-specific mappings.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
errors = []
expected_count = sum(source_counts.values())
if not isinstance(loaded, list):
    errors.append('Output root is not a JSON array')
if len(loaded) != expected_count:
    errors.append(f'Row count mismatch: {len(loaded)} != {expected_count}')
for i, rec in enumerate(loaded, 1):
    if list(rec.keys()) != TARGET_FIELDS:
        errors.append(f'Record {i} keys/order mismatch: {list(rec.keys())}')
    if rec['device_id'] is not None and not isinstance(rec['device_id'], str):
        errors.append(f'Record {i} device_id is not text')
    if rec['status'] in {'OK', 'PASS', 'NG', 'FAIL'}:
        errors.append(f'Record {i} unnormalized status {rec["status"]}')
    if 'value' not in rec or 'unit' not in rec:
        errors.append(f'Record {i} lacks value/unit')

# Specific checks based on input samples: CSV Measurement must become value, blank/missing value/unit become None.
by_id = {r['device_id']: r for r in loaded}
checks = {
    'D001 value from CSV Measurement': by_id.get('D001', {}).get('value') == '12.5',
    'D002 blank Measurement null': by_id.get('D002', {}).get('value') is None,
    'D004 missing unit null': by_id.get('D004', {}).get('unit') is None,
    'D001 OK Pass': by_id.get('D001', {}).get('status') == 'Pass',
    'D002 NG Fail': by_id.get('D002', {}).get('status') == 'Fail',
    'D003 PASS Pass': by_id.get('D003', {}).get('status') == 'Pass',
    'D004 FAIL Fail': by_id.get('D004', {}).get('status') == 'Fail',
}
for name, ok in checks.items():
    if not ok:
        errors.append('Failed check: ' + name)

print('\nPROCESSING SUMMARY:')
print('Source parsed row counts:', source_counts)
print('Total output rows:', len(loaded))
print('Output file:', out_path)
print('Output records:', loaded)
print('value null count:', sum(1 for r in loaded if r['value'] is None))
print('unit null count:', sum(1 for r in loaded if r['unit'] is None))
print('Statuses in output:', sorted({r['status'] for r in loaded}))
print('Input-specific checks:', checks)

if errors:
    print('\nVERIFICATION FAILED:')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print('\nVERIFICATION PASSED: reports.json has exact unified fields, all records preserved, device_id as text, status normalized, CSV/JSON/Markdown values mapped, and missing value/unit as null.')
