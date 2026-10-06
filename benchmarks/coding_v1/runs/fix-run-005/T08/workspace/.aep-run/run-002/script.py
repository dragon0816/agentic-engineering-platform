from pathlib import Path
import csv, json

ws = Path('.')
input_dir = ws / 'input'
output_dir = ws / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

STATUS_MAP = {
    'OK': 'Pass',
    'PASS': 'Pass',
    'NG': 'Fail',
    'FAIL': 'Fail',
}

def norm_status(s):
    if s is None:
        return None
    return STATUS_MAP.get(str(s).strip().upper(), str(s).strip())

def norm_value(v):
    if v is None:
        return None
    if isinstance(v, str):
        t = v.strip()
        if t == '':
            return None
        # Convert numeric-looking values to numbers while leaving non-numeric values intact.
        try:
            n = float(t)
            return int(n) if n.is_integer() else n
        except ValueError:
            return t
    return v

def norm_unit(u):
    if u is None:
        return None
    t = str(u).strip()
    return t if t != '' else None

def record(device_id, test_name, status, value=None, unit=None):
    return {
        'device_id': '' if device_id is None else str(device_id).strip(),
        'test_name': '' if test_name is None else str(test_name).strip(),
        'status': norm_status(status),
        'value': norm_value(value),
        'unit': norm_unit(unit),
    }

results = []

# CSV report
with (input_dir / 'report_a.csv').open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        results.append(record(row.get('DUT'), row.get('Item'), row.get('Result'), row.get('Measurement'), row.get('Unit')))

# JSON report
with (input_dir / 'report_b.json').open('r', encoding='utf-8-sig') as f:
    data = json.load(f)
    for row in data:
        results.append(record(row.get('device'), row.get('test'), row.get('outcome'), row.get('value'), row.get('unit')))

# Markdown table report
md_lines = (input_dir / 'report_c.md').read_text(encoding='utf-8-sig').splitlines()
md_rows = []
for line in md_lines:
    stripped = line.strip()
    if not stripped.startswith('|') or not stripped.endswith('|'):
        continue
    cells = [c.strip() for c in stripped.strip('|').split('|')]
    # skip separator rows like ---
    if cells and all(set(c) <= {'-', ':', ' '} for c in cells):
        continue
    md_rows.append(cells)
if md_rows:
    headers = md_rows[0]
    for cells in md_rows[1:]:
        row = dict(zip(headers, cells))
        results.append(record(row.get('Device'), row.get('Test'), row.get('Status'), row.get('Value'), row.get('Unit')))

out_path = output_dir / 'reports.json'
out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')

# Verification by reopening saved output
loaded = json.loads(out_path.read_text(encoding='utf-8'))
expected_fields = ['device_id', 'test_name', 'status', 'value', 'unit']
checks = []
checks.append(('output_exists', out_path.exists()))
checks.append(('row_count_6', len(loaded) == 6))
checks.append(('fields_exact', all(list(item.keys()) == expected_fields for item in loaded)))
checks.append(('device_ids_are_text', all(isinstance(item['device_id'], str) for item in loaded)))
checks.append(('statuses_normalized', [item['status'] for item in loaded] == ['Pass','Fail','Pass','Fail','Pass','Fail']))
checks.append(('missing_value_null_csv_D002', loaded[1]['value'] is None))
checks.append(('missing_unit_null_json_D004', loaded[3]['unit'] is None))
checks.append(('all_records_preserved', [item['device_id'] for item in loaded] == ['D001','D002','D003','D004','D005','D006']))
checks.append(('only_unified_fields', all(set(item) == set(expected_fields) for item in loaded)))

print('Wrote:', out_path.resolve())
print('Rows:', len(loaded))
print('Preview:')
print(json.dumps(loaded, ensure_ascii=False, indent=2))
print('Checks:')
failed = []
for name, ok in checks:
    print(f'- {name}: {ok}')
    if not ok:
        failed.append(name)
if failed:
    raise SystemExit('Failed checks: ' + ', '.join(failed))
