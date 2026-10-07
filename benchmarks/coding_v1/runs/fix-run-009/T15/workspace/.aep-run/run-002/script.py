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
status_map = {'PASS': 'Pass', 'FAIL': 'Fail'}
parsed = []
warnings = []

with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_no, raw_line in enumerate(f, start=1):
        original = raw_line.rstrip('\r\n')
        if original.strip() == '':
            continue
        m = pattern.match(original)
        if not m:
            warnings.append({
                'line_number': line_no,
                'line': original,
                'reason': 'Line does not match [TIME][DEVICE][TEST][RESULT] format'
            })
            continue
        timestamp, device_id, test_name, result = m.groups()
        if result not in status_map:
            warnings.append({
                'line_number': line_no,
                'line': original,
                'reason': f'Invalid RESULT {result!r}; expected PASS or FAIL'
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

# Verification: reopen output files and confirm required files, columns/keys, status values, warning fields, and counts.
with parsed_path.open('r', encoding='utf-8') as f:
    parsed_check = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    warnings_check = json.load(f)

required_parsed_keys = ['timestamp', 'device_id', 'test_name', 'status']
required_warning_keys = ['line_number', 'line', 'reason']
assert isinstance(parsed_check, list), 'parsed.json must be a JSON array'
assert isinstance(warnings_check, list), 'warnings.json must be a JSON array'
for idx, row in enumerate(parsed_check, start=1):
    assert list(row.keys()) == required_parsed_keys, f'parsed row {idx} has wrong keys: {list(row.keys())}'
    assert row['status'] in {'Pass', 'Fail'}, f'parsed row {idx} has wrong status: {row["status"]}'
    for key in ['timestamp', 'device_id', 'test_name']:
        assert isinstance(row[key], str) and row[key] != '', f'parsed row {idx} {key} must be non-empty text'
for idx, row in enumerate(warnings_check, start=1):
    assert list(row.keys()) == required_warning_keys, f'warning row {idx} has wrong keys: {list(row.keys())}'
    assert isinstance(row['line_number'], int), f'warning row {idx} line_number must be integer'
    assert isinstance(row['line'], str), f'warning row {idx} line must be text'
    assert isinstance(row['reason'], str) and row['reason'], f'warning row {idx} reason must be non-empty text'

# Independently count non-empty input lines and ensure all are either parsed or warned.
non_empty_count = sum(1 for line in input_path.open('r', encoding='utf-8', errors='replace') if line.strip())
assert len(parsed_check) + len(warnings_check) == non_empty_count, 'parsed + warnings must equal non-empty input lines'

print('Wrote:', parsed_path)
print('Wrote:', warnings_path)
print('Parsed records:', len(parsed_check))
print('Warnings:', len(warnings_check))
print('Non-empty input lines checked:', non_empty_count)
print('Parsed keys checked:', required_parsed_keys)
print('Warning keys checked:', required_warning_keys)
print('Statuses checked: only Pass/Fail')
print('Warning line numbers:', [w['line_number'] for w in warnings_check])
