from pathlib import Path
import json
import re

ws = Path.cwd()
input_dir = ws / 'input'
output_dir = ws / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

unified_path = output_dir / 'unified.json'
warnings_path = output_dir / 'warnings.json'

v1_re = re.compile(r'^\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]$')

def normalize_status(value):
    if value is None:
        return None
    s = str(value).strip().lower()
    if s == 'pass':
        return 'Pass'
    if s == 'fail':
        return 'Fail'
    return None

def rel_source(path):
    return path.relative_to(input_dir).as_posix()

records = []
warnings = []

files = sorted(p for p in input_dir.rglob('*') if p.is_file())
print('Input files to process:')
for p in files:
    print('-', rel_source(p))

for p in files:
    source = rel_source(p)
    try:
        text = p.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        text = p.read_text(encoding='utf-8-sig')
    for line_no, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            warnings.append({
                'source_file': source,
                'line_number': line_no,
                'line': raw_line,
                'warning': 'empty line'
            })
            continue

        m = v1_re.match(line)
        if m:
            timestamp, device_id, test_name, result = [x.strip() for x in m.groups()]
            status = normalize_status(result)
            if status is None:
                warnings.append({
                    'source_file': source,
                    'line_number': line_no,
                    'line': raw_line,
                    'warning': f'V1 line has unknown result: {result!r}'
                })
                continue
            records.append({
                'timestamp': timestamp,
                'device_id': device_id,
                'test_name': test_name,
                'status': status,
                'source_file': source,
                'format_version': 'V1'
            })
            continue

        # Try V2 JSON-lines format.
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            warnings.append({
                'source_file': source,
                'line_number': line_no,
                'line': raw_line,
                'warning': 'unknown format: not V1 bracket format and not valid JSON'
            })
            continue

        if not isinstance(obj, dict):
            warnings.append({
                'source_file': source,
                'line_number': line_no,
                'line': raw_line,
                'warning': 'unknown format: JSON line is not an object'
            })
            continue

        required = ['ts', 'dut', 'case', 'result']
        missing = [k for k in required if k not in obj]
        status = normalize_status(obj.get('result'))
        if missing or status is None:
            reason = []
            if missing:
                reason.append('missing fields: ' + ', '.join(missing))
            if status is None:
                reason.append(f'unknown result: {obj.get("result")!r}')
            warnings.append({
                'source_file': source,
                'line_number': line_no,
                'line': raw_line,
                'warning': 'unknown V2 format: ' + '; '.join(reason)
            })
            continue

        records.append({
            'timestamp': str(obj['ts']),
            'device_id': str(obj['dut']),
            'test_name': str(obj['case']),
            'status': status,
            'source_file': source,
            'format_version': 'V2'
        })

with unified_path.open('w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
    f.write('\n')

with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Verification: reopen outputs and check stated requirements.
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
expected_fields = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']
assert isinstance(loaded_records, list), 'unified.json must contain a JSON array'
assert all(list(r.keys()) == expected_fields for r in loaded_records), 'unified.json fields/order mismatch'
assert all(r['status'] in ('Pass', 'Fail') for r in loaded_records), 'status not normalized to Pass/Fail'
assert all(r['format_version'] in ('V1', 'V2') for r in loaded_records), 'bad format_version'
assert all(isinstance(r['source_file'], str) and r['source_file'] for r in loaded_records), 'missing source_file'
assert isinstance(loaded_warnings, list), 'warnings.json must contain a JSON array'
assert all({'source_file','line_number','line','warning'} <= set(w.keys()) for w in loaded_warnings), 'warning record fields missing'

print('\nWrote:', unified_path)
print('Wrote:', warnings_path)
print('Unified record count:', len(loaded_records))
print('Warning count:', len(loaded_warnings))
print('By format:', {v: sum(1 for r in loaded_records if r['format_version'] == v) for v in ['V1','V2']})
print('By status:', {v: sum(1 for r in loaded_records if r['status'] == v) for v in ['Pass','Fail']})
print('\nFirst unified records:')
for r in loaded_records[:3]:
    print(r)
print('\nWarnings:')
for w in loaded_warnings:
    print(w)
print('\nVerification passed: reopened unified.json and warnings.json; checked fields, status values, format versions, source_file presence, and warning fields.')