from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

pattern = re.compile(r'^\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\]$')
parsed = []
warnings = []

with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_no, raw in enumerate(f, start=1):
        line = raw.rstrip('\r\n')
        if line.strip() == '':
            continue
        m = pattern.fullmatch(line)
        if not m:
            warnings.append({
                'line_number': line_no,
                'line': line,
                'reason': 'Line does not match [TIME][DEVICE][TEST][RESULT] format'
            })
            continue
        timestamp, device_id, test_name, result = m.groups()
        if result not in {'PASS', 'FAIL'}:
            warnings.append({
                'line_number': line_no,
                'line': line,
                'reason': f'Invalid result {result!r}; expected PASS or FAIL'
            })
            continue
        parsed.append({
            'timestamp': timestamp,
            'device_id': device_id,
            'test_name': test_name,
            'status': 'Pass' if result == 'PASS' else 'Fail'
        })

with parsed_path.open('w', encoding='utf-8') as f:
    json.dump(parsed, f, ensure_ascii=False, indent=2)
    f.write('\n')
with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Verification: reopen outputs and confirm requested structure and counts from source.
parsed_loaded = json.loads(parsed_path.read_text(encoding='utf-8'))
warnings_loaded = json.loads(warnings_path.read_text(encoding='utf-8'))
expected_parsed_keys = ['timestamp', 'device_id', 'test_name', 'status']
expected_warning_keys = ['line_number', 'line', 'reason']

source_nonempty_count = 0
for raw in input_path.read_text(encoding='utf-8', errors='replace').splitlines():
    if raw.strip():
        source_nonempty_count += 1

assert isinstance(parsed_loaded, list), 'parsed.json is not a JSON list'
assert isinstance(warnings_loaded, list), 'warnings.json is not a JSON list'
for idx, rec in enumerate(parsed_loaded, start=1):
    assert list(rec.keys()) == expected_parsed_keys, f'parsed record {idx} has wrong keys: {list(rec.keys())}'
    assert all(isinstance(rec[k], str) for k in expected_parsed_keys), f'parsed record {idx} values are not all strings'
    assert rec['status'] in {'Pass', 'Fail'}, f'parsed record {idx} status is invalid: {rec["status"]}'
for idx, rec in enumerate(warnings_loaded, start=1):
    assert list(rec.keys()) == expected_warning_keys, f'warning record {idx} has wrong keys: {list(rec.keys())}'
    assert isinstance(rec['line_number'], int), f'warning record {idx} line_number is not int'
    assert isinstance(rec['line'], str), f'warning record {idx} line is not str'
    assert isinstance(rec['reason'], str) and rec['reason'], f'warning record {idx} reason missing'
assert len(parsed_loaded) + len(warnings_loaded) == source_nonempty_count, 'parsed + warnings does not equal non-empty source lines'

print('Wrote:', parsed_path)
print('Wrote:', warnings_path)
print('Non-empty input lines:', source_nonempty_count)
print('Parsed records:', len(parsed_loaded))
print('Warning records:', len(warnings_loaded))
print('Verification passed: output files reopened; required field names, value types, Pass/Fail statuses, warning fields, and non-empty line accounting were checked.')