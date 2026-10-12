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

# --- Inspect inputs: names, headers/samples/raw snippets ---
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
        sample = data[:3] if isinstance(data, list) else (list(data.items())[:3] if isinstance(data, dict) else data)
        print('JSON sample:', sample)
    elif suffix in ('.md', '.markdown'):
        text = p.read_text(encoding='utf-8-sig')
        print('Markdown first 1000 chars:')
        print(text[:1000])
    else:
        print('Unhandled suffix, first 500 chars:')
        print(p.read_text(encoding='utf-8-sig', errors='replace')[:500])

TARGET_FIELDS = ['device_id', 'test_name', 'status', 'value', 'unit']
STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}

# flexible aliases only for reading varied source names; output remains exactly TARGET_FIELDS
ALIASES = {
    'device_id': ['device_id', 'device id', 'deviceid', 'id', 'device', 'dut', 'dut_id', 'serial', 'serial_no', 'serial number'],
    'test_name': ['test_name', 'test name', 'testname', 'test', 'name', 'item', 'measurement', 'metric'],
    'status': ['status', 'result', 'outcome', 'pass_fail', 'pass/fail'],
    'value': ['value', 'val', 'reading', 'measured', 'measurement_value'],
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
    if not isinstance(row, dict):
        return None
    normed = {norm_key(k): v for k, v in row.items()}
    candidates = [norm_key(a) for a in ALIASES[target]]
    for cand in candidates:
        if cand in normed:
            return clean_cell(normed[cand])
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
    # ID must be text; preserve leading zeros/numeric ids as strings where present
    if rec['device_id'] is not None:
        rec['device_id'] = str(rec['device_id'])
    return rec

def flatten_json_records(obj):
    # Accept list of records, dict containing a list, or one record dict.
    if isinstance(obj, list):
        out = []
        for item in obj:
            out.extend(flatten_json_records(item))
        return out
    if isinstance(obj, dict):
        # If it already looks like a row, keep it.
        row_keys = {norm_key(k) for k in obj.keys()}
        alias_keys = {norm_key(a) for aliases in ALIASES.values() for a in aliases}
        if row_keys & alias_keys:
            return [obj]
        # Otherwise inspect nested list/dict values for rows.
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
        line = lines[i].strip()
        if '|' not in line:
            i += 1
            continue
        # collect contiguous pipe rows
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
            if len(cells) < len(header):
                cells += [''] * (len(header) - len(cells))
            records.append(dict(zip(header, cells[:len(header)])))
    return records

def parse_markdown_key_value_records(text):
    # Fallback for bullet/key-value style records separated by blank lines or headings.
    records = []
    current = {}
    key_re = re.compile(r'^\s*(?:[-*]\s*)?\**\s*([A-Za-z][A-Za-z0-9_ /-]*?)\s*\**\s*[:：]\s*(.*?)\s*$')
    for line in text.splitlines() + ['']:
        m = key_re.match(line)
        if m:
            key, val = m.group(1).strip(), m.group(2).strip()
            current[key] = val
        elif line.strip() == '' and current:
            if {norm_key(k) for k in current} & {norm_key(a) for aliases in ALIASES.values() for a in aliases}:
                records.append(current)
            current = {}
    return records

all_records = []
source_counts = {}
for p in sorted(input_dir.iterdir()):
    suffix = p.suffix.lower()
    rows = []
    if suffix == '.csv':
        with p.open('r', encoding='utf-8-sig', newline='') as f:
            rows = list(csv.DictReader(f))
    elif suffix == '.json':
        data = json.loads(p.read_text(encoding='utf-8-sig'))
        rows = flatten_json_records(data)
    elif suffix in ('.md', '.markdown'):
        text = p.read_text(encoding='utf-8-sig')
        rows = parse_markdown_tables(text)
        if not rows:
            rows = parse_markdown_key_value_records(text)
    else:
        continue
    source_counts[p.name] = len(rows)
    for row in rows:
        all_records.append(normalize_record(row))

out_path = output_dir / 'reports.json'
with out_path.open('w', encoding='utf-8') as f:
    json.dump(all_records, f, ensure_ascii=False, indent=2)

# --- Verification: reopen output and assert every stated requirement ---
loaded = json.loads(out_path.read_text(encoding='utf-8'))
expected_count = sum(source_counts.values())
errors = []
if not isinstance(loaded, list):
    errors.append('Output root is not a JSON array')
if len(loaded) != expected_count:
    errors.append(f'Row count mismatch: output {len(loaded)} != input parsed {expected_count}')
for idx, rec in enumerate(loaded, 1):
    if list(rec.keys()) != TARGET_FIELDS:
        errors.append(f'Record {idx} keys/order mismatch: {list(rec.keys())}')
    if rec.get('device_id') is not None and not isinstance(rec.get('device_id'), str):
        errors.append(f'Record {idx} device_id is not text: {rec.get("device_id")!r}')
    if rec.get('status') in {'OK', 'PASS', 'NG', 'FAIL'}:
        errors.append(f'Record {idx} has unnormalized status: {rec.get("status")!r}')
    if 'value' not in rec or 'unit' not in rec:
        errors.append(f'Record {idx} missing value/unit key')

print('\nPROCESSING SUMMARY:')
print('Source parsed row counts:', source_counts)
print('Total output rows:', len(loaded))
print('Output file:', out_path)
print('First output records:', loaded[:5])

# Extra null report for value/unit missing
value_nulls = sum(1 for r in loaded if r['value'] is None)
unit_nulls = sum(1 for r in loaded if r['unit'] is None)
print('value null count:', value_nulls)
print('unit null count:', unit_nulls)
statuses = sorted({r['status'] for r in loaded}, key=lambda x: '' if x is None else str(x))
print('Statuses in output:', statuses)

if errors:
    print('\nVERIFICATION FAILED:')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print('\nVERIFICATION PASSED: reports.json has exact fields, all parsed rows, text device_id, normalized status, and value/unit keys with null when missing.')
