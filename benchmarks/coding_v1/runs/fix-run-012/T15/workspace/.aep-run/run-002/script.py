from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

pattern = re.compile(r'^\[([^\[\]]+)\]\[([^\[\]]+)\]\[([^\[\]]+)\]\[([^\[\]]+)\]$')

parsed = []
warnings = []

with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_no, raw in enumerate(f, start=1):
        line = raw.rstrip('\n\r')
        if line.strip() == '':
            continue
        m = pattern.fullmatch(line)
        if not m:
            warnings.append({
                'line_number': line_no,
                'line': line,
                'reason': 'Line does not match required format [TIME][DEVICE][TEST][RESULT]'
            })
            continue
        timestamp, device_id, test_name, result = m.groups()
        if result == 'PASS':
            status = 'Pass'
        elif result == 'FAIL':
            status = 'Fail'
        else:
            warnings.append({
                'line_number': line_no,
                'line': line,
                'reason': 'RESULT must be PASS or FAIL'
            })
            continue
        parsed.append({
            'timestamp': timestamp,
            'device_id': device_id,
            'test_name': test_name,
            'status': status
        })

with parsed_path.open('w', encoding='utf-8') as f:
    json.dump(parsed, f, ensure_ascii=False, indent=2)
    f.write('\n')

with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Verification: reopen outputs and confirm requirements
with parsed_path.open('r', encoding='utf-8') as f:
    parsed_check = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    warnings_check = json.load(f)

expected_parsed_keys = ['timestamp', 'device_id', 'test_name', 'status']
expected_warning_keys = ['line_number', 'line', 'reason']

assert isinstance(parsed_check, list), 'parsed.json must contain a JSON array'
assert isinstance(warnings_check, list), 'warnings.json must contain a JSON array'
for idx, row in enumerate(parsed_check, start=1):
    assert list(row.keys()) == expected_parsed_keys, f'parsed row {idx} keys mismatch: {list(row.keys())}'
    assert all(isinstance(row[k], str) for k in expected_parsed_keys), f'parsed row {idx} values must be strings'
    assert row['status'] in ('Pass', 'Fail'), f'parsed row {idx} invalid status: {row["status"]}'
for idx, row in enumerate(warnings_check, start=1):
    assert list(row.keys()) == expected_warning_keys, f'warning row {idx} keys mismatch: {list(row.keys())}'
    assert isinstance(row['line_number'], int), f'warning row {idx} line_number must be int'
    assert isinstance(row['line'], str), f'warning row {idx} line must be string'
    assert isinstance(row['reason'], str) and row['reason'], f'warning row {idx} reason must be non-empty string'

non_empty_count = sum(1 for line in input_path.read_text(encoding='utf-8', errors='replace').splitlines() if line.strip())
assert len(parsed_check) + len(warnings_check) == non_empty_count, 'parsed + warnings must equal non-empty input lines'

print('wrote:', parsed_path)
print('wrote:', warnings_path)
print('non_empty_input_lines:', non_empty_count)
print('parsed_count:', len(parsed_check))
print('warning_count:', len(warnings_check))
print('parsed_statuses:', sorted({row['status'] for row in parsed_check}))
print('warning_line_numbers:', [row['line_number'] for row in warnings_check])
print('verification: passed')
