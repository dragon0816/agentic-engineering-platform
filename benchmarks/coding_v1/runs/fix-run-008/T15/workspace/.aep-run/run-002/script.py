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
    for line_no, raw_line in enumerate(f, start=1):
        line = raw_line.rstrip('\r\n')
        if line.strip() == '':
            continue
        match = pattern.fullmatch(line)
        if not match:
            warnings.append({
                'line_number': line_no,
                'line': line,
                'reason': 'Line does not match [TIME][DEVICE][TEST][RESULT] format'
            })
            continue
        timestamp, device_id, test_name, result = match.groups()
        if result not in {'PASS', 'FAIL'}:
            warnings.append({
                'line_number': line_no,
                'line': line,
                'reason': 'Result is not PASS or FAIL'
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

# Verification: reopen outputs and confirm required structure/content.
with parsed_path.open('r', encoding='utf-8') as f:
    parsed_check = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    warnings_check = json.load(f)

assert isinstance(parsed_check, list), 'parsed.json must contain a JSON array'
assert isinstance(warnings_check, list), 'warnings.json must contain a JSON array'
required_parsed_keys = ['timestamp', 'device_id', 'test_name', 'status']
for idx, item in enumerate(parsed_check, start=1):
    assert list(item.keys()) == required_parsed_keys, f'parsed item {idx} has wrong fields: {list(item.keys())}'
    assert item['status'] in {'Pass', 'Fail'}, f'parsed item {idx} status not Pass/Fail'
    for key in ['timestamp', 'device_id', 'test_name', 'status']:
        assert isinstance(item[key], str), f'parsed item {idx} {key} is not text'
required_warning_keys = ['line_number', 'line', 'reason']
for idx, item in enumerate(warnings_check, start=1):
    assert list(item.keys()) == required_warning_keys, f'warning item {idx} has wrong fields: {list(item.keys())}'
    assert isinstance(item['line_number'], int), f'warning item {idx} line_number is not int'
    assert isinstance(item['line'], str), f'warning item {idx} line is not text'
    assert isinstance(item['reason'], str) and item['reason'], f'warning item {idx} reason missing'

# Confirm row accounting over non-empty source lines.
non_empty_count = sum(1 for line in input_path.open('r', encoding='utf-8', errors='replace') if line.strip())
assert len(parsed_check) + len(warnings_check) == non_empty_count, 'parsed + warnings does not equal non-empty input lines'

print('Wrote:', parsed_path)
print('Wrote:', warnings_path)
print('Parsed records:', len(parsed_check))
print('Warning records:', len(warnings_check))
print('Non-empty input lines checked:', non_empty_count)
print('parsed.json fields checked:', required_parsed_keys)
print('warnings.json fields checked:', required_warning_keys)
print('Statuses checked: Pass/Fail only')
print('Warnings preview:', warnings_check)