from pathlib import Path
import json
import re

ws = Path.cwd()
inp = ws / 'input'
out = ws / 'output'
out.mkdir(parents=True, exist_ok=True)

# First, print the real inputs recursively and sample contents.
files = sorted([p for p in inp.rglob('*') if p.is_file()]) if inp.exists() else []
print('workspace:', ws)
print('input exists:', inp.exists())
print('output exists:', out.exists())
print('recursive input files:', [str(p.relative_to(inp)) for p in files])
for p in files:
    print('\n--- sample', str(p.relative_to(inp)), '---')
    try:
        with p.open('r', encoding='utf-8-sig') as f:
            for i, line in zip(range(1, 6), f):
                print(f'{i}: {line.rstrip()}')
    except UnicodeDecodeError:
        with p.open('r', encoding='utf-8', errors='replace') as f:
            for i, line in zip(range(1, 6), f):
                print(f'{i}: {line.rstrip()}')

# Complete processing script.
V1_RE = re.compile(r'^\s*\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\]\s*$')

PASS_VALUES = {'pass', 'passed', 'ok', 'success', 'true', '1'}
FAIL_VALUES = {'fail', 'failed', 'ng', 'error', 'false', '0'}

def normalize_status(value):
    s = str(value).strip()
    key = s.lower()
    if key in PASS_VALUES:
        return 'Pass'
    if key in FAIL_VALUES:
        return 'Fail'
    # Common prefix fallback, but do not turn empty or unrelated values into Pass/Fail.
    if key.startswith('pass'):
        return 'Pass'
    if key.startswith('fail'):
        return 'Fail'
    return None

records = []
warnings = []

for path in files:
    rel = path.relative_to(inp).as_posix()
    try:
        raw_text = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        raw_text = path.read_text(encoding='utf-8', errors='replace')
    for line_no, line in enumerate(raw_text.splitlines(), start=1):
        original = line
        line = line.strip()
        if not line:
            continue

        parsed = None
        fmt = None
        status = None

        m = V1_RE.match(line)
        if m:
            ts, dut, case, result = [x.strip() for x in m.groups()]
            status = normalize_status(result)
            if status is not None:
                parsed = {
                    'timestamp': ts,
                    'device_id': dut,
                    'test_name': case,
                    'status': status,
                    'source_file': rel,
                    'format_version': 'V1',
                }
                fmt = 'V1'
        else:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as e:
                obj = None
                json_error = str(e)
            if isinstance(obj, dict):
                required = ['ts', 'dut', 'case', 'result']
                if all(k in obj for k in required):
                    status = normalize_status(obj.get('result'))
                    if status is not None:
                        parsed = {
                            'timestamp': str(obj.get('ts', '')),
                            'device_id': str(obj.get('dut', '')),
                            'test_name': str(obj.get('case', '')),
                            'status': status,
                            'source_file': rel,
                            'format_version': 'V2',
                        }
                        fmt = 'V2'
                else:
                    missing = [k for k in required if k not in obj]
                    warnings.append({
                        'source_file': rel,
                        'line_number': line_no,
                        'warning': 'unknown format: JSON line missing required field(s): ' + ', '.join(missing),
                        'line': original,
                    })
                    continue
            elif obj is not None:
                warnings.append({
                    'source_file': rel,
                    'line_number': line_no,
                    'warning': 'unknown format: JSON line is not an object',
                    'line': original,
                })
                continue

        if parsed is not None:
            records.append(parsed)
        else:
            reason = 'unknown format'
            if m and status is None:
                reason = 'unknown status in V1 line'
            elif 'obj' in locals() and isinstance(obj, dict) and status is None:
                reason = 'unknown status in V2 line'
            warnings.append({
                'source_file': rel,
                'line_number': line_no,
                'warning': reason,
                'line': original,
            })

unified_path = out / 'unified.json'
warnings_path = out / 'warnings.json'
summary_path = out / 'summary.json'

unified_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')
summary = {
    'input_files': [str(p.relative_to(inp).as_posix()) for p in files],
    'record_count': len(records),
    'warning_count': len(warnings),
    'output_files': ['unified.json', 'warnings.json', 'summary.json'],
}
summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

print('\nWROTE:', unified_path)
print('WROTE:', warnings_path)
print('WROTE:', summary_path)
print('record_count:', len(records))
print('warning_count:', len(warnings))

# Reopen and verify outputs against stated requirements.
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
expected_cols = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']
assert isinstance(loaded_records, list), 'unified.json must be a JSON array'
for idx, rec in enumerate(loaded_records):
    assert list(rec.keys()) == expected_cols, f'record {idx} fields differ: {list(rec.keys())}'
    assert rec['status'] in ('Pass', 'Fail'), f'record {idx} status not normalized: {rec["status"]}'
    assert rec['format_version'] in ('V1', 'V2'), f'record {idx} bad format_version: {rec["format_version"]}'
    for col in expected_cols:
        assert isinstance(rec[col], str), f'record {idx} {col} is not text'
assert isinstance(loaded_warnings, list), 'warnings.json must be a JSON array'
for idx, warn in enumerate(loaded_warnings):
    for col in ['source_file', 'line_number', 'warning', 'line']:
        assert col in warn, f'warning {idx} missing {col}'
    assert isinstance(warn['line_number'], int), f'warning {idx} line_number is not int'
print('CHECK PASSED: unified.json reopened; columns, text values, Pass/Fail status, V1/V2 version, and warnings structure verified.')
