from pathlib import Path
import json

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
parsed_path = workspace / 'output' / 'parsed.json'
warnings_path = workspace / 'output' / 'warnings.json'

assert parsed_path.exists(), 'parsed.json missing'
assert warnings_path.exists(), 'warnings.json missing'

with parsed_path.open('r', encoding='utf-8') as f:
    parsed = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    warnings = json.load(f)

assert isinstance(parsed, list), 'parsed.json must be a list'
assert isinstance(warnings, list), 'warnings.json must be a list'

parsed_keys = {'timestamp', 'device_id', 'test_name', 'status'}
warning_keys = {'line_number', 'line', 'reason'}

for idx, row in enumerate(parsed, start=1):
    assert set(row.keys()) == parsed_keys, f'parsed row {idx} has wrong keys: {row.keys()}'
    for key in ['timestamp', 'device_id', 'test_name', 'status']:
        assert isinstance(row[key], str), f'parsed row {idx} {key} is not string'
    assert row['status'] in {'Pass', 'Fail'}, f'parsed row {idx} invalid status: {row["status"]}'

for idx, row in enumerate(warnings, start=1):
    assert set(row.keys()) == warning_keys, f'warning row {idx} has wrong keys: {row.keys()}'
    assert isinstance(row['line_number'], int), f'warning row {idx} line_number is not int'
    assert isinstance(row['line'], str), f'warning row {idx} line is not string'
    assert isinstance(row['reason'], str) and row['reason'], f'warning row {idx} reason invalid'

non_empty_count = 0
with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line in f:
        if line.strip():
            non_empty_count += 1

assert len(parsed) + len(warnings) == non_empty_count, (
    f'parsed + warnings ({len(parsed)} + {len(warnings)}) != non-empty lines ({non_empty_count})'
)

print('CHECK PASSED')
print('parsed.json exists:', parsed_path)
print('warnings.json exists:', warnings_path)
print('parsed rows:', len(parsed))
print('warning rows:', len(warnings))
print('non-empty input lines:', non_empty_count)
print('statuses:', sorted({row['status'] for row in parsed}))
print('warning line_numbers:', [row['line_number'] for row in warnings])