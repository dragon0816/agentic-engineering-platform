from pathlib import Path
import json, re
from datetime import datetime

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)

# Inspection: print real input files, first lines, and JSON/log shape clues.
print('Workspace:', workspace)
print('Input directory:', input_dir, 'exists=', input_dir.exists())
input_files = [p for p in sorted(input_dir.rglob('*')) if p.is_file()]
print('Input files:', [str(p.relative_to(input_dir)) for p in input_files])
for p in input_files:
    try:
        text = p.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        text = p.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()
    print('\nINSPECT', str(p.relative_to(input_dir)), 'size=', p.stat().st_size, 'lines=', len(lines))
    for i, line in enumerate(lines[:5], 1):
        print(f'  {i}: {line[:300]}')

# Parsers
v1_pattern = re.compile(r'^\s*\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\]\s*$')
pass_tokens = {'pass', 'passed', 'ok', 'success', 'succeeded', 'true', '1'}
fail_tokens = {'fail', 'failed', 'ng', 'error', 'false', '0'}

def normalize_status(value):
    raw = '' if value is None else str(value).strip()
    token = raw.lower()
    if token in pass_tokens:
        return 'Pass'
    if token in fail_tokens:
        return 'Fail'
    # Also handle common embedded forms without treating unknown as valid.
    compact = re.sub(r'[^a-z0-9]+', '', token)
    if compact in pass_tokens:
        return 'Pass'
    if compact in fail_tokens:
        return 'Fail'
    return None

def nonempty_text(value):
    if value is None:
        return ''
    return str(value).strip()

records = []
warnings = []

for path in input_files:
    rel = str(path.relative_to(input_dir)).replace('\\', '/')
    try:
        text = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        text = path.read_text(encoding='utf-8', errors='replace')
    for line_no, line in enumerate(text.splitlines(), 1):
        raw_line = line.rstrip('\n\r')
        if not raw_line.strip():
            continue
        parsed = None
        warning_reason = None

        # V2: each line JSON with ts, dut, case, result.
        stripped = raw_line.strip()
        if stripped.startswith('{'):
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict) and all(k in obj for k in ('ts', 'dut', 'case', 'result')):
                    status = normalize_status(obj.get('result'))
                    if status is None:
                        warning_reason = 'V2 JSON line has unknown result/status value'
                    else:
                        parsed = {
                            'timestamp': nonempty_text(obj.get('ts')),
                            'device_id': nonempty_text(obj.get('dut')),
                            'test_name': nonempty_text(obj.get('case')),
                            'status': status,
                            'source_file': rel,
                            'format_version': 'V2',
                        }
                else:
                    warning_reason = 'JSON line missing required V2 fields ts, dut, case, result'
            except json.JSONDecodeError as exc:
                warning_reason = f'invalid JSON line: {exc.msg}'

        # V1: [TIME][DEVICE][TEST][RESULT]
        if parsed is None and warning_reason is None:
            m = v1_pattern.match(raw_line)
            if m:
                timestamp, device_id, test_name, result = [part.strip() for part in m.groups()]
                status = normalize_status(result)
                if status is None:
                    warning_reason = 'V1 line has unknown result/status value'
                else:
                    parsed = {
                        'timestamp': timestamp,
                        'device_id': device_id,
                        'test_name': test_name,
                        'status': status,
                        'source_file': rel,
                        'format_version': 'V1',
                    }
            else:
                warning_reason = 'unknown log format'

        if parsed is not None:
            records.append(parsed)
        else:
            warnings.append({
                'source_file': rel,
                'line_number': line_no,
                'line': raw_line,
                'warning': warning_reason or 'unknown log format',
            })

# Stable output ordering follows sorted input files and original line order.
unified_path = output_dir / 'unified.json'
warnings_path = output_dir / 'warnings.json'
unified_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')

# Verification from saved outputs.
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
required_keys = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']
assert isinstance(loaded_records, list), 'unified.json must contain a JSON list'
for idx, rec in enumerate(loaded_records, 1):
    assert list(rec.keys()) == required_keys, f'record {idx} keys/order mismatch: {rec.keys()}'
    assert rec['status'] in ('Pass', 'Fail'), f'record {idx} has non-normalized status'
    assert rec['format_version'] in ('V1', 'V2'), f'record {idx} has invalid format_version'
    for key in required_keys:
        assert isinstance(rec[key], str), f'record {idx} field {key} is not text'
assert isinstance(loaded_warnings, list), 'warnings.json must contain a JSON list'
for idx, warn in enumerate(loaded_warnings, 1):
    assert {'source_file', 'line_number', 'line', 'warning'} <= set(warn), f'warning {idx} missing keys'
    assert isinstance(warn['line_number'], int), f'warning {idx} line_number not int'
print('\nWROTE', unified_path.relative_to(workspace), 'records=', len(loaded_records))
print('WROTE', warnings_path.relative_to(workspace), 'warnings=', len(loaded_warnings))
print('Verified unified.json keys/order, text fields, Pass/Fail statuses, V1/V2 format versions, and warnings schema.')
if loaded_records[:3]:
    print('Sample unified records:', json.dumps(loaded_records[:3], ensure_ascii=False))
if loaded_warnings[:3]:
    print('Sample warnings:', json.dumps(loaded_warnings[:3], ensure_ascii=False))