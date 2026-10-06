from pathlib import Path
import json
import re

WORKSPACE = Path.cwd()
INPUT_DIR = WORKSPACE / 'input'
OUTPUT_DIR = WORKSPACE / 'output'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

unified_path = OUTPUT_DIR / 'unified.json'
warnings_path = OUTPUT_DIR / 'warnings.json'

v1_re = re.compile(r'^\[(?P<timestamp>[^\]]+)\]\[(?P<device_id>[^\]]+)\]\[(?P<test_name>[^\]]+)\]\[(?P<status>[^\]]+)\]$')


def normalize_status(value):
    if value is None:
        return None
    text = str(value).strip().lower()
    if text in {'pass', 'passed', 'ok', 'success', 'true', '1'}:
        return 'Pass'
    if text in {'fail', 'failed', 'ng', 'nok', 'false', '0'}:
        return 'Fail'
    return None


def source_name(path):
    # Keep the source compact but unique inside input/.
    return path.relative_to(INPUT_DIR).as_posix()

records = []
warnings = []

for path in sorted(INPUT_DIR.rglob('*')):
    if not path.is_file():
        continue
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except UnicodeDecodeError:
        lines = path.read_text(encoding='utf-8-sig', errors='replace').splitlines()

    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line:
            warnings.append({
                'source_file': source_name(path),
                'line_number': line_number,
                'line': raw_line,
                'warning': 'empty line / unknown format',
            })
            continue

        parsed = None
        m = v1_re.match(line)
        if m:
            status = normalize_status(m.group('status'))
            if status:
                parsed = {
                    'timestamp': m.group('timestamp').strip(),
                    'device_id': m.group('device_id').strip(),
                    'test_name': m.group('test_name').strip(),
                    'status': status,
                    'source_file': source_name(path),
                    'format_version': 'V1',
                }

        if parsed is None:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict) and {'ts', 'dut', 'case', 'result'} <= set(obj.keys()):
                status = normalize_status(obj.get('result'))
                if status:
                    parsed = {
                        'timestamp': str(obj.get('ts', '')).strip(),
                        'device_id': str(obj.get('dut', '')).strip(),
                        'test_name': str(obj.get('case', '')).strip(),
                        'status': status,
                        'source_file': source_name(path),
                        'format_version': 'V2',
                    }

        if parsed is None:
            warnings.append({
                'source_file': source_name(path),
                'line_number': line_number,
                'line': raw_line,
                'warning': 'unknown format or unsupported status',
            })
        else:
            records.append(parsed)

with unified_path.open('w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
    f.write('\n')

with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Verification: reopen output files and confirm stated requirements.
expected_fields = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))

assert isinstance(loaded_records, list), 'unified.json must be a JSON array'
assert isinstance(loaded_warnings, list), 'warnings.json must be a JSON array'
assert len(loaded_records) == 6, f'expected 6 parsed rows, got {len(loaded_records)}'
assert len(loaded_warnings) == 2, f'expected 2 warnings, got {len(loaded_warnings)}'
for idx, rec in enumerate(loaded_records, 1):
    assert list(rec.keys()) == expected_fields, f'record {idx} field order/name mismatch: {list(rec.keys())}'
    assert rec['status'] in {'Pass', 'Fail'}, f'record {idx} has unnormalised status {rec["status"]!r}'
    assert rec['format_version'] in {'V1', 'V2'}, f'record {idx} has bad format_version {rec["format_version"]!r}'
    for field in expected_fields:
        assert isinstance(rec[field], str), f'record {idx} field {field} is not text'

warning_sources = {(w.get('source_file'), w.get('line_number')) for w in loaded_warnings}
assert warning_sources == {('logs/run_c.log', 1), ('logs/run_c.log', 2)}, f'unexpected warnings: {warning_sources}'
for idx, warn in enumerate(loaded_warnings, 1):
    assert {'source_file', 'line_number', 'line', 'warning'} <= set(warn), f'warning {idx} missing fields'

print('Wrote:', unified_path)
print('Wrote:', warnings_path)
print('Parsed records:', len(loaded_records))
print('Warnings:', len(loaded_warnings))
print('Unified fields:', expected_fields)
print('Statuses:', sorted({r['status'] for r in loaded_records}))
print('Format versions:', sorted({r['format_version'] for r in loaded_records}))
print('Warning locations:', sorted(warning_sources))