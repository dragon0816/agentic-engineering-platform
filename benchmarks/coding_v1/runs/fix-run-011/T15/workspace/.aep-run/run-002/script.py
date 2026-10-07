from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
output_dir = workspace / 'output'
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

output_dir.mkdir(parents=True, exist_ok=True)

pattern = re.compile(r'^\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]$')
parsed = []
warnings = []

with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_no, raw in enumerate(f, start=1):
        original = raw.rstrip('\r\n')
        content = original.strip()
        if content == '':
            continue

        match = pattern.fullmatch(content)
        if not match:
            warnings.append({
                'line_number': line_no,
                'line': original,
                'reason': 'does not match [TIME][DEVICE][TEST][RESULT]'
            })
            continue

        timestamp, device_id, test_name, result = match.groups()
        empty_fields = []
        if timestamp == '':
            empty_fields.append('TIME')
        if device_id == '':
            empty_fields.append('DEVICE')
        if test_name == '':
            empty_fields.append('TEST')
        if result == '':
            empty_fields.append('RESULT')
        if empty_fields:
            warnings.append({
                'line_number': line_no,
                'line': original,
                'reason': 'empty field(s): ' + ', '.join(empty_fields)
            })
            continue

        if result not in {'PASS', 'FAIL'}:
            warnings.append({
                'line_number': line_no,
                'line': original,
                'reason': f'invalid RESULT {result!r}; expected PASS or FAIL'
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

# Reopen and validate saved outputs against the stated requirements.
with parsed_path.open('r', encoding='utf-8') as f:
    saved_parsed = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    saved_warnings = json.load(f)

expected_parsed_keys = ['timestamp', 'device_id', 'test_name', 'status']
expected_warning_keys = ['line_number', 'line', 'reason']
assert isinstance(saved_parsed, list), 'parsed.json must contain a JSON array'
assert isinstance(saved_warnings, list), 'warnings.json must contain a JSON array'
for i, item in enumerate(saved_parsed, start=1):
    assert list(item.keys()) == expected_parsed_keys, f'parsed item {i} keys mismatch: {list(item.keys())}'
    assert all(isinstance(item[k], str) for k in expected_parsed_keys), f'parsed item {i} values must be strings'
    assert item['status'] in {'Pass', 'Fail'}, f'parsed item {i} status must be Pass/Fail'
for i, item in enumerate(saved_warnings, start=1):
    assert list(item.keys()) == expected_warning_keys, f'warning item {i} keys mismatch: {list(item.keys())}'
    assert isinstance(item['line_number'], int), f'warning item {i} line_number must be int'
    assert isinstance(item['line'], str), f'warning item {i} line must be str'
    assert isinstance(item['reason'], str) and item['reason'], f'warning item {i} reason must be non-empty str'

non_empty_lines = 0
with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for raw in f:
        if raw.strip():
            non_empty_lines += 1
assert len(saved_parsed) + len(saved_warnings) == non_empty_lines, 'parsed + warnings must equal non-empty input lines'

print('Wrote:', parsed_path)
print('Wrote:', warnings_path)
print('Parsed records:', len(saved_parsed))
print('Warnings:', len(saved_warnings))
print('Non-empty input lines:', non_empty_lines)
print('Validation checked: output files exist and reopen; JSON arrays; parsed keys/types/status values; warning keys/types/reasons; parsed+warnings count equals non-empty input lines.')
if saved_warnings:
    print('Warning details:')
    for w in saved_warnings:
        print(f"- line {w['line_number']}: {w['reason']} | {w['line']}")
