from pathlib import Path
import json
import re

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

unified_path = output_dir / 'unified.json'
warnings_path = output_dir / 'warnings.json'

v1_re = re.compile(r'^\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\]\[([^\]]*)\]$')
required_v2 = {'ts', 'dut', 'case', 'result'}

def norm_status(value):
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {'pass', 'passed', 'ok', 'success'}:
        return 'Pass'
    if s in {'fail', 'failed', 'ng', 'error'}:
        return 'Fail'
    return None

def rel_source(path):
    try:
        return str(path.relative_to(input_dir)).replace('\\', '/')
    except ValueError:
        return path.name

records = []
warnings = []

print('Scanning input:', input_dir)
files = [p for p in sorted(input_dir.rglob('*')) if p.is_file()]
print('Input files:', [rel_source(p) for p in files])

for path in files:
    source = rel_source(path)
    try:
        text = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        text = path.read_text(encoding='latin-1')
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line:
            continue
        parsed = None
        warning_reason = None

        m = v1_re.match(line)
        if m:
            ts, device, test, result = (part.strip() for part in m.groups())
            status = norm_status(result)
            if status is None:
                warning_reason = f'V1 line has unsupported result: {result}'
            else:
                parsed = {
                    'timestamp': ts,
                    'device_id': device,
                    'test_name': test,
                    'status': status,
                    'source_file': source,
                    'format_version': 'V1',
                }
        else:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict) and required_v2.issubset(obj.keys()):
                status = norm_status(obj.get('result'))
                if status is None:
                    warning_reason = f'V2 line has unsupported result: {obj.get("result")}'
                else:
                    parsed = {
                        'timestamp': str(obj.get('ts', '')).strip(),
                        'device_id': str(obj.get('dut', '')).strip(),
                        'test_name': str(obj.get('case', '')).strip(),
                        'status': status,
                        'source_file': source,
                        'format_version': 'V2',
                    }
            else:
                warning_reason = 'unknown format'

        if parsed is not None:
            records.append(parsed)
        else:
            warnings.append({
                'source_file': source,
                'line_number': line_no,
                'line': raw,
                'warning': warning_reason or 'unparsed line',
            })

unified_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')

print('Wrote:', unified_path)
print('Wrote:', warnings_path)
print('Unified records:', len(records))
print('Warnings:', len(warnings))

# Verification: reopen every output and confirm requirements.
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
expected_fields = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']
assert isinstance(loaded_records, list), 'unified.json must be a JSON array'
assert isinstance(loaded_warnings, list), 'warnings.json must be a JSON array'
for idx, rec in enumerate(loaded_records, start=1):
    assert list(rec.keys()) == expected_fields, f'record {idx} fields/order mismatch: {list(rec.keys())}'
    assert rec['status'] in {'Pass', 'Fail'}, f'record {idx} status not normalized: {rec["status"]}'
    assert rec['format_version'] in {'V1', 'V2'}, f'record {idx} format_version invalid: {rec["format_version"]}'
    for key in expected_fields:
        assert isinstance(rec[key], str), f'record {idx} {key} is not text'
for idx, warn in enumerate(loaded_warnings, start=1):
    for key in ['source_file', 'line_number', 'line', 'warning']:
        assert key in warn, f'warning {idx} missing {key}'
    assert isinstance(warn['line_number'], int), f'warning {idx} line_number not integer'

# Confirm all non-empty input lines accounted for as record or warning.
non_empty_lines = 0
for p in files:
    try:
        text = p.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        text = p.read_text(encoding='latin-1')
    non_empty_lines += sum(1 for line in text.splitlines() if line.strip())
assert len(loaded_records) + len(loaded_warnings) == non_empty_lines, 'not all input lines accounted for'

print('Verification OK')
print('  unified.json fields:', expected_fields)
print('  statuses:', sorted({r['status'] for r in loaded_records}))
print('  format versions:', sorted({r['format_version'] for r in loaded_records}))
print('  input non-empty lines accounted for:', non_empty_lines)
print('  warning lines:', len(loaded_warnings))
