from pathlib import Path
import json
import re

ws = Path.cwd()
input_path = ws / 'input' / 'test.log'
output_dir = ws / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

pattern = re.compile(r'^\[([^\]\[]+)\]\[([^\]\[]+)\]\[([^\]\[]+)\]\[(PASS|FAIL)\]$')
parsed = []
warnings = []

with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_no, raw_line in enumerate(f, start=1):
        line = raw_line.rstrip('\r\n')
        if line.strip() == '':
            continue
        m = pattern.fullmatch(line)
        if not m:
            reason = 'line does not match format [TIME][DEVICE][TEST][RESULT] with RESULT PASS or FAIL'
            # More specific reasons when obvious, without risking exceptions.
            bracketed = re.findall(r'\[([^\]]*)\]', line)
            if len(bracketed) != 4:
                reason = f'expected 4 bracketed fields, found {len(bracketed)}'
            elif bracketed[3] not in {'PASS', 'FAIL'}:
                reason = f'invalid result {bracketed[3]!r}; expected PASS or FAIL'
            warnings.append({
                'line_number': line_no,
                'line': line,
                'reason': reason,
            })
            continue
        timestamp, device_id, test_name, result = m.groups()
        parsed.append({
            'timestamp': timestamp,
            'device_id': device_id,
            'test_name': test_name,
            'status': 'Pass' if result == 'PASS' else 'Fail',
        })

parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')

# Verification: reopen outputs and confirm stated requirements.
loaded_parsed = json.loads(parsed_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
expected_parsed_keys = ['timestamp', 'device_id', 'test_name', 'status']
expected_warning_keys = ['line_number', 'line', 'reason']
assert isinstance(loaded_parsed, list), 'parsed.json must be a JSON array'
assert isinstance(loaded_warnings, list), 'warnings.json must be a JSON array'
for idx, row in enumerate(loaded_parsed, start=1):
    assert list(row.keys()) == expected_parsed_keys, f'parsed row {idx} keys mismatch: {list(row.keys())}'
    assert row['status'] in {'Pass', 'Fail'}, f'parsed row {idx} has invalid status {row["status"]!r}'
    assert all(isinstance(row[k], str) for k in expected_parsed_keys), f'parsed row {idx} values must be strings'
for idx, row in enumerate(loaded_warnings, start=1):
    assert list(row.keys()) == expected_warning_keys, f'warning row {idx} keys mismatch: {list(row.keys())}'
    assert isinstance(row['line_number'], int), f'warning row {idx} line_number must be int'
    assert isinstance(row['line'], str), f'warning row {idx} line must be str'
    assert isinstance(row['reason'], str) and row['reason'], f'warning row {idx} reason must be non-empty str'

# Confirm count against source's non-empty lines.
source_lines = input_path.read_text(encoding='utf-8', errors='replace').splitlines()
non_empty_count = sum(1 for line in source_lines if line.strip())
assert len(loaded_parsed) + len(loaded_warnings) == non_empty_count, 'parsed + warnings must equal non-empty source lines'

print('created:', parsed_path)
print('created:', warnings_path)
print('parsed rows:', len(loaded_parsed))
print('warning rows:', len(loaded_warnings))
print('non-empty source lines:', non_empty_count)
print('parsed statuses:', sorted(set(row['status'] for row in loaded_parsed)))
print('warning line numbers:', [row['line_number'] for row in loaded_warnings])
