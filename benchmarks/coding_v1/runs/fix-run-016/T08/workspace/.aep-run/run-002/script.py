from pathlib import Path
import csv, json, re

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

FIELDS = ['device_id', 'test_name', 'status', 'value', 'unit']
STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}

def norm_status(s):
    if s is None:
        return None
    key = str(s).strip().upper()
    return STATUS_MAP.get(key, str(s).strip() if str(s).strip() else None)

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
        # keep numeric values numeric; use int if exact integer textual value
        f = float(s)
        if re.fullmatch(r'[+-]?\d+', s):
            return int(s)
        return f
    except ValueError:
        return s

def record(device_id, test_name, status, value=None, unit=None):
    return {
        'device_id': '' if device_id is None else str(device_id).strip(),
        'test_name': '' if test_name is None else str(test_name).strip(),
        'status': norm_status(status),
        'value': norm_value(value),
        'unit': norm_text(unit),
    }

def parse_csv(path):
    out = []
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.DictReader(f)
        print(f'CSV {path.name} headers: {reader.fieldnames}')
        for row in reader:
            out.append(record(row.get('DUT'), row.get('Item'), row.get('Result'), row.get('Measurement'), row.get('Unit')))
    print(f'CSV {path.name} records: {len(out)}')
    return out

def parse_json(path):
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data, dict):
        # If JSON is wrapped, use the first list value; otherwise single record.
        lists = [v for v in data.values() if isinstance(v, list)]
        rows = lists[0] if lists else [data]
    elif isinstance(data, list):
        rows = data
    else:
        raise ValueError(f'Unsupported JSON top-level in {path.name}: {type(data).__name__}')
    out = [record(r.get('device'), r.get('test'), r.get('outcome'), r.get('value'), r.get('unit')) for r in rows]
    print(f'JSON {path.name} records: {len(out)}')
    return out

def parse_markdown(path):
    lines = [ln.strip() for ln in path.read_text(encoding='utf-8-sig').splitlines() if ln.strip()]
    table_lines = [ln for ln in lines if ln.startswith('|') and ln.endswith('|')]
    if len(table_lines) < 2:
        return []
    headers = [c.strip() for c in table_lines[0].strip('|').split('|')]
    print(f'MD {path.name} headers: {headers}')
    out = []
    for ln in table_lines[2:]:
        cells = [c.strip() for c in ln.strip('|').split('|')]
        row = dict(zip(headers, cells))
        out.append(record(row.get('Device'), row.get('Test'), row.get('Status'), row.get('Value'), row.get('Unit')))
    print(f'MD {path.name} records: {len(out)}')
    return out

reports = []
for path in sorted(input_dir.iterdir()):
    suffix = path.suffix.lower()
    if suffix == '.csv':
        reports.extend(parse_csv(path))
    elif suffix == '.json':
        reports.extend(parse_json(path))
    elif suffix in {'.md', '.markdown'}:
        reports.extend(parse_markdown(path))
    else:
        print(f'Skipping unsupported file: {path.name}')

out_path = output_dir / 'reports.json'
out_path.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Wrote {out_path} with {len(reports)} records')

# Verification: reopen output and check stated requirements.
loaded = json.loads(out_path.read_text(encoding='utf-8'))
errors = []
if not isinstance(loaded, list):
    errors.append('reports.json is not a JSON array')
if len(loaded) != 6:
    errors.append(f'expected 6 records preserving all results, got {len(loaded)}')
for i, rec in enumerate(loaded, start=1):
    if list(rec.keys()) != FIELDS:
        errors.append(f'record {i} keys/order {list(rec.keys())} != {FIELDS}')
    if not isinstance(rec.get('device_id'), str):
        errors.append(f'record {i} device_id is not text: {rec.get("device_id")!r}')
    if rec.get('status') not in {'Pass', 'Fail'}:
        errors.append(f'record {i} status not normalized: {rec.get("status")!r}')
    if rec.get('value') is not None and not isinstance(rec.get('value'), (int, float, str)):
        errors.append(f'record {i} value has unexpected type: {type(rec.get("value")).__name__}')
    if rec.get('unit') is not None and not isinstance(rec.get('unit'), str):
        errors.append(f'record {i} unit has unexpected type: {type(rec.get("unit")).__name__}')

by_id = {rec['device_id']: rec for rec in loaded}
expected_status = {'D001':'Pass','D002':'Fail','D003':'Pass','D004':'Fail','D005':'Pass','D006':'Fail'}
for did, st in expected_status.items():
    if did not in by_id:
        errors.append(f'missing device_id {did}')
    elif by_id[did]['status'] != st:
        errors.append(f'{did} status expected {st}, got {by_id[did]["status"]}')
if by_id.get('D002', {}).get('value', 'MISSING') is not None:
    errors.append(f'D002 blank value should be null, got {by_id.get("D002", {}).get("value")!r}')
if by_id.get('D004', {}).get('unit', 'MISSING') is not None:
    errors.append(f'D004 missing unit should be null, got {by_id.get("D004", {}).get("unit")!r}')

if errors:
    print('VERIFICATION FAILED')
    for e in errors:
        print(' -', e)
    raise SystemExit(1)
print('VERIFICATION PASSED')
print('Checked: output filename reports.json, JSON array, 6 records retained, exact unified fields/order, device_id text, status mappings OK/PASS->Pass and NG/FAIL->Fail, missing/blank value or unit as null.')
print('Output preview:')
print(json.dumps(loaded, ensure_ascii=False, indent=2))