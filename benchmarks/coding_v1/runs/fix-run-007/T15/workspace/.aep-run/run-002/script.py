from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

line_re = re.compile(r'^\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\]$')
status_map = {'PASS': 'Pass', 'FAIL': 'Fail'}

parsed = []
warnings = []
non_empty_count = 0

with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_number, raw_line in enumerate(f, start=1):
        original = raw_line.rstrip('\r\n')
        stripped = original.strip()
        if stripped == '':
            continue
        non_empty_count += 1

        match = line_re.fullmatch(stripped)
        if not match:
            warnings.append({
                'line_number': line_number,
                'line': original,
                'reason': 'Line does not match required [TIME][DEVICE][TEST][RESULT] format'
            })
            continue

        timestamp, device_id, test_name, result = (part.strip() for part in match.groups())
        if not timestamp:
            warnings.append({'line_number': line_number, 'line': original, 'reason': 'TIME field is empty'})
            continue
        if not device_id:
            warnings.append({'line_number': line_number, 'line': original, 'reason': 'DEVICE field is empty'})
            continue
        if not test_name:
            warnings.append({'line_number': line_number, 'line': original, 'reason': 'TEST field is empty'})
            continue
        if not result:
            warnings.append({'line_number': line_number, 'line': original, 'reason': 'RESULT field is empty'})
            continue

        status_key = result.upper()
        if status_key not in status_map:
            warnings.append({
                'line_number': line_number,
                'line': original,
                'reason': 'RESULT must be PASS or FAIL'
            })
            continue

        parsed.append({
            'timestamp': timestamp,
            'device_id': device_id,
            'test_name': test_name,
            'status': status_map[status_key]
        })

with parsed_path.open('w', encoding='utf-8') as f:
    json.dump(parsed, f, ensure_ascii=False, indent=2)
    f.write('\n')

with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

print('Wrote:', parsed_path)
print('Wrote:', warnings_path)
print('Non-empty lines:', non_empty_count)
print('Parsed rows:', len(parsed))
print('Warnings:', len(warnings))
print('Warning line numbers:', [w['line_number'] for w in warnings])
print('Parsed preview:', parsed[:3])
print('Warnings preview:', warnings[:3])