from pathlib import Path
import json, re
from datetime import datetime

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

print('workspace:', workspace)
print('input exists:', input_dir.exists())
all_paths = sorted([p for p in input_dir.rglob('*')]) if input_dir.exists() else []
print('input path count:', len(all_paths))
for path in all_paths:
    rel = path.relative_to(input_dir)
    print(('DIR :' if path.is_dir() else 'FILE:'), rel, (f'size={path.stat().st_size}' if path.is_file() else ''))
    if path.is_file():
        try:
            with path.open('r', encoding='utf-8-sig') as f:
                for i in range(1, 4):
                    line = f.readline()
                    if not line:
                        break
                    print(f'  sample line {i}: {line.rstrip()}')
        except Exception as e:
            print('  sample read error:', repr(e))

# Parser implementation
v1_re = re.compile(r'^\s*\[(?P<time>[^\]]+)\]\[(?P<device>[^\]]+)\]\[(?P<test>[^\]]+)\]\[(?P<result>[^\]]+)\]\s*$')

def norm_status(value):
    s = str(value).strip().lower()
    if s in {'pass', 'passed', 'ok', 'success', 'true', '1'}:
        return 'Pass'
    if s in {'fail', 'failed', 'ng', 'error', 'false', '0'}:
        return 'Fail'
    return None

def make_record(timestamp, device_id, test_name, status, source_file, format_version):
    return {
        'timestamp': '' if timestamp is None else str(timestamp),
        'device_id': '' if device_id is None else str(device_id),
        'test_name': '' if test_name is None else str(test_name),
        'status': status,
        'source_file': source_file,
        'format_version': format_version,
    }

records = []
warnings = []
files = [p for p in sorted(input_dir.rglob('*')) if p.is_file()] if input_dir.exists() else []

for path in files:
    rel_source = str(path.relative_to(input_dir)).replace('\\', '/')
    try:
        lines = path.read_text(encoding='utf-8-sig').splitlines()
    except UnicodeDecodeError:
        lines = path.read_text(encoding='utf-8').splitlines()
    except Exception as e:
        warnings.append({'source_file': rel_source, 'line_number': None, 'line': None, 'reason': f'file read error: {e}'})
        continue
    for line_no, line in enumerate(lines, start=1):
        raw = line.rstrip('\n')
        if not raw.strip():
            continue
        parsed = False
        m = v1_re.match(raw)
        if m:
            status = norm_status(m.group('result'))
            if status is None:
                warnings.append({'source_file': rel_source, 'line_number': line_no, 'line': raw, 'reason': f'unknown V1 result value: {m.group("result")}'})
            else:
                records.append(make_record(m.group('time'), m.group('device'), m.group('test'), status, rel_source, 'V1'))
            parsed = True
        else:
            try:
                obj = json.loads(raw)
                if isinstance(obj, dict) and all(k in obj for k in ('ts', 'dut', 'case', 'result')):
                    status = norm_status(obj.get('result'))
                    if status is None:
                        warnings.append({'source_file': rel_source, 'line_number': line_no, 'line': raw, 'reason': f'unknown V2 result value: {obj.get("result")}'})
                    else:
                        records.append(make_record(obj.get('ts'), obj.get('dut'), obj.get('case'), status, rel_source, 'V2'))
                    parsed = True
                else:
                    warnings.append({'source_file': rel_source, 'line_number': line_no, 'line': raw, 'reason': 'JSON line does not contain required V2 fields ts, dut, case, result'})
                    parsed = True
            except json.JSONDecodeError:
                pass
        if not parsed:
            warnings.append({'source_file': rel_source, 'line_number': line_no, 'line': raw, 'reason': 'unknown format'})

unified_path = output_dir / 'unified.json'
warnings_path = output_dir / 'warnings.json'
unified_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Verification by reopening outputs
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
required_keys = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']
assert isinstance(loaded_records, list), 'unified.json is not a JSON array'
for idx, rec in enumerate(loaded_records):
    assert list(rec.keys()) == required_keys, f'record {idx} columns mismatch: {list(rec.keys())}'
    assert rec['status'] in ('Pass', 'Fail'), f'record {idx} status not normalized: {rec["status"]}'
    assert rec['format_version'] in ('V1', 'V2'), f'record {idx} bad format_version: {rec["format_version"]}'
    for key in required_keys:
        assert isinstance(rec[key], str), f'record {idx} {key} is not text'
assert isinstance(loaded_warnings, list), 'warnings.json is not a JSON array'
for idx, warn in enumerate(loaded_warnings):
    for key in ['source_file', 'line_number', 'line', 'reason']:
        assert key in warn, f'warning {idx} missing {key}'

print('\nWROTE:', unified_path)
print('WROTE:', warnings_path)
print('records:', len(loaded_records))
print('warnings:', len(loaded_warnings))
print('checked unified keys:', required_keys)
print('checked statuses: all Pass/Fail')
print('checked format versions: all V1/V2')
print('checked warning fields: source_file, line_number, line, reason')
