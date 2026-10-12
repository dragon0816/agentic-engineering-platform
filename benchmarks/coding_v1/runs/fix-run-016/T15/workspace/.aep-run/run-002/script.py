from pathlib import Path
import json
import re

workspace = Path.cwd()
input_path = workspace / 'input' / 'test.log'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
parsed_path = output_dir / 'parsed.json'
warnings_path = output_dir / 'warnings.json'

pattern = re.compile(r'^\[([^\[\]]+)\]\[([^\[\]]+)\]\[([^\[\]]+)\]\[(PASS|FAIL)\]$')

parsed = []
warnings = []

with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for line_no, raw in enumerate(f, start=1):
        text = raw.rstrip('\n\r')
        if text.strip() == '':
            continue
        m = pattern.fullmatch(text)
        if not m:
            reason = 'Line does not match required [TIME][DEVICE][TEST][RESULT] format with RESULT PASS or FAIL'
            # Give more specific reasons where possible, but keep processing all lines.
            bracket_values = re.findall(r'\[([^\[\]]*)\]', text)
            if len(bracket_values) != 4:
                reason = f'Expected 4 bracketed fields, found {len(bracket_values)}'
            elif bracket_values[3] not in {'PASS', 'FAIL'}:
                reason = f'Invalid result {bracket_values[3]!r}; expected PASS or FAIL'
            warnings.append({
                'line_number': line_no,
                'line': text,
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

with parsed_path.open('w', encoding='utf-8') as f:
    json.dump(parsed, f, ensure_ascii=False, indent=2)
    f.write('\n')
with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

print('Wrote:', parsed_path, 'records=', len(parsed))
print('Wrote:', warnings_path, 'warnings=', len(warnings))
print('parsed preview:', json.dumps(parsed[:3], ensure_ascii=False))
print('warnings preview:', json.dumps(warnings[:5], ensure_ascii=False))

# Verification: reopen output files and confirm stated requirements.
with parsed_path.open('r', encoding='utf-8') as f:
    parsed_check = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    warnings_check = json.load(f)

assert isinstance(parsed_check, list), 'parsed.json must contain a JSON array'
assert isinstance(warnings_check, list), 'warnings.json must contain a JSON array'
expected_parsed_keys = ['timestamp', 'device_id', 'test_name', 'status']
for idx, rec in enumerate(parsed_check, start=1):
    assert list(rec.keys()) == expected_parsed_keys, f'parsed record {idx} keys mismatch: {list(rec.keys())}'
    assert all(isinstance(rec[k], str) for k in expected_parsed_keys), f'parsed record {idx} values must be strings'
    assert rec['status'] in {'Pass', 'Fail'}, f'parsed record {idx} status must be Pass/Fail'
expected_warning_keys = ['line_number', 'line', 'reason']
for idx, rec in enumerate(warnings_check, start=1):
    assert list(rec.keys()) == expected_warning_keys, f'warning record {idx} keys mismatch: {list(rec.keys())}'
    assert isinstance(rec['line_number'], int), f'warning record {idx} line_number must be int'
    assert isinstance(rec['line'], str), f'warning record {idx} line must be str'
    assert isinstance(rec['reason'], str) and rec['reason'], f'warning record {idx} reason must be non-empty str'

# Count non-empty input lines and ensure each became either parsed or warning.
nonempty_count = 0
with input_path.open('r', encoding='utf-8', errors='replace') as f:
    for raw in f:
        if raw.strip():
            nonempty_count += 1
assert len(parsed_check) + len(warnings_check) == nonempty_count, 'Every non-empty line must be parsed or warned'
print('Verification OK: reopened parsed.json and warnings.json; columns/keys, status values, warning types, and row counts checked.')
print('nonempty input lines=', nonempty_count, 'parsed=', len(parsed_check), 'warnings=', len(warnings_check))