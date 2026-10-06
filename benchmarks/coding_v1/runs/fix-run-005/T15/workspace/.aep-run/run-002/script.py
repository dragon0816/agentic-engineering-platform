from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

pattern = re.compile(r'^\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]$')
parsed = []
warnings = []

with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_no, line in enumerate(f, start=1):
        raw = line.rstrip('\n\r')
        if raw.strip() == '':
            continue
        match = pattern.fullmatch(raw)
        if not match:
            warnings.append({
                'line_number': line_no,
                'line': raw,
                'reason': 'Line does not match [TIME][DEVICE][TEST][RESULT] format'
            })
            continue
        timestamp, device_id, test_name, result = match.groups()
        if result not in {'PASS', 'FAIL'}:
            warnings.append({
                'line_number': line_no,
                'line': raw,
                'reason': f'Invalid RESULT {result!r}; expected PASS or FAIL'
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

# Verification from saved outputs
with parsed_path.open('r', encoding='utf-8') as f:
    saved_parsed = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    saved_warnings = json.load(f)

expected_parsed_keys = ['timestamp', 'device_id', 'test_name', 'status']
expected_warning_keys = ['line_number', 'line', 'reason']
assert isinstance(saved_parsed, list), 'parsed.json must contain a JSON array'
assert isinstance(saved_warnings, list), 'warnings.json must contain a JSON array'
for idx, row in enumerate(saved_parsed, start=1):
    assert list(row.keys()) == expected_parsed_keys, f'parsed row {idx} has wrong fields: {list(row.keys())}'
    assert all(isinstance(row[k], str) for k in expected_parsed_keys), f'parsed row {idx} values must be strings'
    assert row['status'] in {'Pass', 'Fail'}, f'parsed row {idx} invalid status: {row["status"]}'
for idx, row in enumerate(saved_warnings, start=1):
    assert list(row.keys()) == expected_warning_keys, f'warning row {idx} has wrong fields: {list(row.keys())}'
    assert isinstance(row['line_number'], int), f'warning row {idx} line_number must be int'
    assert isinstance(row['line'], str), f'warning row {idx} line must be string'
    assert isinstance(row['reason'], str) and row['reason'], f'warning row {idx} reason must be non-empty string'

# Recount non-empty lines and parse/warning accounting from source without changing input
non_empty_count = sum(1 for line in input_path.open('r', encoding='utf-8', errors='replace') if line.strip())
assert len(saved_parsed) + len(saved_warnings) == non_empty_count, 'Every non-empty line must become parsed row or warning'

print('Wrote:', parsed_path)
print('Wrote:', warnings_path)
print('Non-empty source lines:', non_empty_count)
print('Parsed rows:', len(saved_parsed))
print('Warning rows:', len(saved_warnings))
print('Parsed sample:', saved_parsed[:2])
print('Warnings:', saved_warnings)
print('Verification passed: output files exist, JSON arrays load, parsed fields/status values are correct, warning fields/types are correct, and every non-empty input line is accounted for.')