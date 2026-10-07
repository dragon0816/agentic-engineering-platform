from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

pattern = re.compile(r'^\[([^\[\]]+)\]\[([^\[\]]+)\]\[([^\[\]]+)\]\[(PASS|FAIL)\]$')
parsed = []
warnings = []

with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_no, raw_line in enumerate(f, start=1):
        line = raw_line.rstrip('\n\r')
        if line.strip() == '':
            continue
        match = pattern.fullmatch(line)
        if not match:
            reason = 'Line does not match [TIME][DEVICE][TEST][RESULT] format with RESULT PASS or FAIL'
            # More specific reasons where safe to identify.
            fields = re.findall(r'\[([^\[\]]*)\]', line)
            if len(fields) != 4:
                reason = f'Expected 4 bracketed fields, found {len(fields)}'
            elif fields[3] not in {'PASS', 'FAIL'}:
                reason = f'Invalid RESULT {fields[3]!r}; expected PASS or FAIL'
            warnings.append({
                'line_number': line_no,
                'line': line,
                'reason': reason,
            })
            continue
        timestamp, device_id, test_name, result = match.groups()
        parsed.append({
            'timestamp': timestamp,
            'device_id': device_id,
            'test_name': test_name,
            'status': 'Pass' if result == 'PASS' else 'Fail',
        })

with parsed_path.open('w', encoding='utf-8') as f:
    json.dump(parsed, f, ensure_ascii=False, indent=2)
with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)

print(f'wrote {parsed_path} records={len(parsed)}')
print(f'wrote {warnings_path} records={len(warnings)}')
print('warning line_numbers:', [w['line_number'] for w in warnings])

# Verification: reopen outputs and validate requirements.
with parsed_path.open('r', encoding='utf-8') as f:
    parsed_check = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    warnings_check = json.load(f)

expected_parsed_keys = ['timestamp', 'device_id', 'test_name', 'status']
expected_warning_keys = ['line_number', 'line', 'reason']
assert isinstance(parsed_check, list), 'parsed.json must be a JSON list'
assert isinstance(warnings_check, list), 'warnings.json must be a JSON list'
for idx, rec in enumerate(parsed_check, start=1):
    assert list(rec.keys()) == expected_parsed_keys, f'parsed record {idx} keys mismatch: {list(rec.keys())}'
    assert rec['status'] in {'Pass', 'Fail'}, f'parsed record {idx} invalid status'
    for key in ['timestamp', 'device_id', 'test_name', 'status']:
        assert isinstance(rec[key], str), f'parsed record {idx} {key} is not text'
for idx, rec in enumerate(warnings_check, start=1):
    assert list(rec.keys()) == expected_warning_keys, f'warning record {idx} keys mismatch: {list(rec.keys())}'
    assert isinstance(rec['line_number'], int), f'warning record {idx} line_number is not integer'
    assert isinstance(rec['line'], str), f'warning record {idx} line is not text'
    assert isinstance(rec['reason'], str) and rec['reason'], f'warning record {idx} reason missing'

# Cross-check against input: all non-empty lines accounted for exactly once.
nonempty_lines = []
with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_no, raw_line in enumerate(f, start=1):
        line = raw_line.rstrip('\n\r')
        if line.strip():
            nonempty_lines.append((line_no, line))
assert len(parsed_check) + len(warnings_check) == len(nonempty_lines), 'not all non-empty lines accounted for'
print('verification passed: output files reopened; fields, value types, statuses, warning records, and non-empty line accounting checked')