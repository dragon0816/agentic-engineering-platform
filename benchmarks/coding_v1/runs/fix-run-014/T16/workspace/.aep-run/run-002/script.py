from pathlib import Path
import json
import re
from datetime import datetime

ws = Path.cwd()
input_dir = ws / 'input'
output_dir = ws / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

v1_pattern = re.compile(r'^\[(?P<time>[^\]]+)\]\[(?P<device>[^\]]+)\]\[(?P<test>[^\]]+)\]\[(?P<result>[^\]]+)\]\s*$')

PASS_VALUES = {'pass', 'passed', 'ok', 'success', 'succeeded', 'true', '1'}
FAIL_VALUES = {'fail', 'failed', 'ng', 'error', 'false', '0'}

def normalize_status(value):
    s = str(value).strip()
    key = s.lower()
    if key in PASS_VALUES:
        return 'Pass'
    if key in FAIL_VALUES:
        return 'Fail'
    return None

def parse_line(line):
    # V2: each line is JSON with ts, dut, case, result
    stripped = line.strip()
    if not stripped:
        return None, 'blank line'

    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict) and all(k in obj for k in ('ts', 'dut', 'case', 'result')):
            status = normalize_status(obj.get('result'))
            if status is None:
                return None, f'V2 line has unknown result value: {obj.get("result")!r}'
            return {
                'timestamp': str(obj.get('ts')),
                'device_id': str(obj.get('dut')),
                'test_name': str(obj.get('case')),
                'status': status,
                'format_version': 'V2',
            }, None
        # valid JSON but not V2 schema; may still be unknown
    except json.JSONDecodeError:
        pass

    # V1: [TIME][DEVICE][TEST][RESULT]
    m = v1_pattern.match(stripped)
    if m:
        status = normalize_status(m.group('result'))
        if status is None:
            return None, f'V1 line has unknown result value: {m.group("result")!r}'
        return {
            'timestamp': m.group('time'),
            'device_id': m.group('device'),
            'test_name': m.group('test'),
            'status': status,
            'format_version': 'V1',
        }, None

    return None, 'unknown format'

records = []
warnings = []
input_files = sorted([p for p in input_dir.iterdir() if p.is_file()]) if input_dir.exists() else []
print('Processing files:', [p.name for p in input_files])

for path in input_files:
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        text = path.read_text(encoding='utf-8-sig')
    for line_no, line in enumerate(text.splitlines(), 1):
        parsed, warning = parse_line(line)
        if parsed is not None:
            parsed['source_file'] = path.name
            # final field order required by the prompt
            records.append({
                'timestamp': parsed['timestamp'],
                'device_id': parsed['device_id'],
                'test_name': parsed['test_name'],
                'status': parsed['status'],
                'source_file': parsed['source_file'],
                'format_version': parsed['format_version'],
            })
        else:
            warnings.append({
                'source_file': path.name,
                'line_number': line_no,
                'line': line,
                'warning': warning,
            })

unified_path = output_dir / 'unified.json'
warnings_path = output_dir / 'warnings.json'
unified_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')

print(f'Wrote {unified_path} with {len(records)} records')
print(f'Wrote {warnings_path} with {len(warnings)} warnings')

# Verification: reopen outputs and confirm requested schema/status/file names.
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
expected_keys = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']
assert isinstance(loaded_records, list), 'unified.json must be a JSON array'
for idx, rec in enumerate(loaded_records):
    assert list(rec.keys()) == expected_keys, f'unified record {idx} keys/order mismatch: {list(rec.keys())}'
    assert rec['status'] in ('Pass', 'Fail'), f'unified record {idx} status not normalized: {rec["status"]}'
    assert rec['format_version'] in ('V1', 'V2'), f'unified record {idx} unknown format_version: {rec["format_version"]}'
    for key in expected_keys:
        assert isinstance(rec[key], str), f'unified record {idx} {key} is not text'
assert isinstance(loaded_warnings, list), 'warnings.json must be a JSON array'
for idx, warn in enumerate(loaded_warnings):
    assert set(warn.keys()) == {'source_file', 'line_number', 'line', 'warning'}, f'warning {idx} keys mismatch'
    assert isinstance(warn['line_number'], int), f'warning {idx} line_number must be int'
print('Verification passed: unified.json schema/order, status values, format_version values, text fields, warning schema, and row counts checked.')
