from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

parsed = []
warnings = []

# Strict four-bracket-field format. Field contents may not contain square brackets.
pattern = re.compile(r'^\[([^\[\]]*)\]\[([^\[\]]*)\]\[([^\[\]]*)\]\[([^\[\]]*)\]$')

try:
    lines = input_path.read_text(encoding='utf-8-sig').splitlines()
except UnicodeDecodeError:
    lines = input_path.read_text(encoding='utf-8').splitlines()
except FileNotFoundError:
    lines = []
    warnings.append({
        'line_number': 0,
        'line': str(input_path),
        'reason': 'input file not found',
    })

for line_no, raw_line in enumerate(lines, start=1):
    if raw_line.strip() == '':
        continue

    line = raw_line.strip()
    match = pattern.fullmatch(line)
    if not match:
        warnings.append({
            'line_number': line_no,
            'line': raw_line,
            'reason': 'line does not match [TIME][DEVICE][TEST][RESULT] format',
        })
        continue

    timestamp, device_id, test_name, result = match.groups()
    result_normalized = result.strip().upper()
    if result_normalized not in {'PASS', 'FAIL'}:
        warnings.append({
            'line_number': line_no,
            'line': raw_line,
            'reason': 'result must be PASS or FAIL',
        })
        continue

    parsed.append({
        'timestamp': timestamp,
        'device_id': device_id,
        'test_name': test_name,
        'status': 'Pass' if result_normalized == 'PASS' else 'Fail',
    })

parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')

print(f'Read: {input_path}')
print(f'Parsed records: {len(parsed)} -> {parsed_path}')
print(f'Warnings: {len(warnings)} -> {warnings_path}')
