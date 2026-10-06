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

# Match exactly four bracketed fields with no extra non-whitespace text.
pattern = re.compile(r'^\[([^\[\]]*)\]\[([^\[\]]*)\]\[([^\[\]]*)\]\[([^\[\]]*)\]$')

try:
    lines = input_path.read_text(encoding='utf-8').splitlines()
except UnicodeDecodeError:
    lines = input_path.read_text(encoding='utf-8-sig').splitlines()
except FileNotFoundError:
    # Still produce outputs and report the problem without crashing.
    lines = []
    warnings.append({
        'line_number': 0,
        'line': '',
        'reason': f'Input file not found: {input_path}'
    })

for line_number, raw_line in enumerate(lines, start=1):
    if raw_line.strip() == '':
        continue

    line = raw_line.strip()
    match = pattern.fullmatch(line)
    if not match:
        warnings.append({
            'line_number': line_number,
            'line': raw_line,
            'reason': 'Line does not match expected format [TIME][DEVICE][TEST][RESULT]'
        })
        continue

    timestamp, device_id, test_name, result = match.groups()
    result_normalized = result.strip().upper()
    if result_normalized not in {'PASS', 'FAIL'}:
        warnings.append({
            'line_number': line_number,
            'line': raw_line,
            'reason': 'RESULT must be PASS or FAIL'
        })
        continue

    parsed.append({
        'timestamp': timestamp,
        'device_id': device_id,
        'test_name': test_name,
        'status': 'Pass' if result_normalized == 'PASS' else 'Fail'
    })

parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')

print(f'Parsed records: {len(parsed)}')
print(f'Warnings: {len(warnings)}')
print(f'Wrote: {parsed_path}')
print(f'Wrote: {warnings_path}')
