from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

pattern = re.compile(r'^\[([^\[\]]*)\]\[([^\[\]]*)\]\[([^\[\]]*)\]\[([^\[\]]*)\]$')
status_map = {'PASS': 'Pass', 'FAIL': 'Fail'}
parsed = []
warnings = []
non_empty_count = 0

with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_no, raw_line in enumerate(f, start=1):
        line = raw_line.rstrip('\n\r')
        if not line.strip():
            continue
        non_empty_count += 1
        m = pattern.fullmatch(line)
        if not m:
            warnings.append({
                'line_number': line_no,
                'line': line,
                'reason': 'Line does not match required format [TIME][DEVICE][TEST][RESULT]'
            })
            continue
        timestamp, device_id, test_name, result = m.groups()
        if result not in status_map:
            warnings.append({
                'line_number': line_no,
                'line': line,
                'reason': f'Result must be PASS or FAIL, got {result!r}'
            })
            continue
        parsed.append({
            'timestamp': timestamp,
            'device_id': device_id,
            'test_name': test_name,
            'status': status_map[result]
        })

with parsed_path.open('w', encoding='utf-8') as f:
    json.dump(parsed, f, ensure_ascii=False, indent=2)
    f.write('\n')

with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Verification: reopen outputs and confirm stated requirements.
with parsed_path.open('r', encoding='utf-8') as f:
    parsed_check = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    warnings_check = json.load(f)

required_parsed_keys = ['timestamp', 'device_id', 'test_name', 'status']
required_warning_keys = ['line_number', 'line', 'reason']

assert isinstance(parsed_check, list), 'parsed.json must contain a JSON array'
assert isinstance(warnings_check, list), 'warnings.json must contain a JSON array'
for idx, rec in enumerate(parsed_check, start=1):
    assert list(rec.keys()) == required_parsed_keys, f'parsed record {idx} keys mismatch: {list(rec.keys())}'
    assert rec['status'] in ('Pass', 'Fail'), f'parsed record {idx} has invalid status {rec["status"]!r}'
    assert all(isinstance(rec[k], str) for k in required_parsed_keys), f'parsed record {idx} values must be strings'
for idx, rec in enumerate(warnings_check, start=1):
    assert list(rec.keys()) == required_warning_keys, f'warning record {idx} keys mismatch: {list(rec.keys())}'
    assert isinstance(rec['line_number'], int), f'warning record {idx} line_number must be integer'
    assert isinstance(rec['line'], str), f'warning record {idx} line must be string'
    assert isinstance(rec['reason'], str) and rec['reason'], f'warning record {idx} reason must be non-empty string'
assert len(parsed_check) + len(warnings_check) == non_empty_count, 'Every non-empty input line must become parsed or warning output'

print('Wrote:', parsed_path)
print('Wrote:', warnings_path)
print('Non-empty input lines:', non_empty_count)
print('Parsed records:', len(parsed_check))
print('Warnings:', len(warnings_check))
print('Warning line numbers:', [w['line_number'] for w in warnings_check])
print('Verification passed: output files reopened; parsed fields/status values checked; warning fields/reasons checked; parsed+warnings equals non-empty line count.')
