from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

# Strictly match exactly four bracketed fields on a non-empty line.
pattern = re.compile(r'^\[([^\[\]]*)\]\[([^\[\]]*)\]\[([^\[\]]*)\]\[([^\[\]]*)\]$')

parsed = []
warnings = []

try:
    text = input_path.read_text(encoding='utf-8')
except UnicodeDecodeError:
    text = input_path.read_text(encoding='utf-8-sig')

for line_no, raw_line in enumerate(text.splitlines(), start=1):
    line = raw_line.strip()
    if line == '':
        continue

    match = pattern.fullmatch(line)
    if not match:
        # Count bracket groups if possible to provide a useful reason.
        groups = re.findall(r'\[([^\[\]]*)\]', line)
        if len(groups) != 4:
            reason = f'Expected 4 bracketed fields, found {len(groups)}'
        else:
            reason = 'Malformed bracket format'
        warnings.append({
            'line_number': line_no,
            'line': raw_line,
            'reason': reason,
        })
        continue

    timestamp, device_id, test_name, result = match.groups()
    if result not in {'PASS', 'FAIL'}:
        warnings.append({
            'line_number': line_no,
            'line': raw_line,
            'reason': f'Invalid RESULT {result!r}; expected PASS or FAIL',
        })
        continue

    parsed.append({
        'timestamp': timestamp,
        'device_id': device_id,
        'test_name': test_name,
        'status': 'Pass' if result == 'PASS' else 'Fail',
    })

parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Verification: reopen outputs and confirm stated requirements.
parsed_check = json.loads(parsed_path.read_text(encoding='utf-8'))
warnings_check = json.loads(warnings_path.read_text(encoding='utf-8'))
non_empty_count = sum(1 for line in text.splitlines() if line.strip())
valid_statuses = {'Pass', 'Fail'}
parsed_required_keys = {'timestamp', 'device_id', 'test_name', 'status'}
warning_required_keys = {'line_number', 'line', 'reason'}

assert isinstance(parsed_check, list), 'parsed.json must be a JSON array'
assert isinstance(warnings_check, list), 'warnings.json must be a JSON array'
assert all(set(row.keys()) == parsed_required_keys for row in parsed_check), 'parsed rows must have exact required fields'
assert all(row['status'] in valid_statuses for row in parsed_check), 'status must be Pass/Fail'
assert all(isinstance(row['timestamp'], str) and isinstance(row['device_id'], str) and isinstance(row['test_name'], str) for row in parsed_check), 'parsed fields must be text'
assert all(set(row.keys()) == warning_required_keys for row in warnings_check), 'warning rows must have exact required fields'
assert all(isinstance(row['line_number'], int) and isinstance(row['line'], str) and isinstance(row['reason'], str) for row in warnings_check), 'warning field types invalid'
assert len(parsed_check) + len(warnings_check) == non_empty_count, 'every non-empty input line must be parsed or warned'

print('Wrote:', parsed_path)
print('Wrote:', warnings_path)
print('Non-empty input lines:', non_empty_count)
print('Parsed rows:', len(parsed_check))
print('Warning rows:', len(warnings_check))
print('Checks passed: output files exist, JSON arrays reopen, parsed fields exactly timestamp/device_id/test_name/status, status values are Pass/Fail, warning fields include original line_number/line/reason, and parsed+warnings equals non-empty input lines.')