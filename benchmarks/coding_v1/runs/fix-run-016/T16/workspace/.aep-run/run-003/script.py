from pathlib import Path
import json
import re

INPUT_DIR = Path('input')
OUTPUT_DIR = Path('output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

v1_re = re.compile(r'^\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]$')
required_fields = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']


def normalize_status(value):
    s = str(value).strip().lower()
    if s == 'pass':
        return 'Pass'
    if s == 'fail':
        return 'Fail'
    return None


def rel_source(path: Path) -> str:
    try:
        return path.relative_to(INPUT_DIR).as_posix()
    except ValueError:
        return path.name

records = []
warnings = []

files = sorted([p for p in INPUT_DIR.rglob('*') if p.is_file()])
print('Processing files:', [str(p) for p in files])

for path in files:
    try:
        text = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        text = path.read_text(encoding='utf-8', errors='replace')
    source = rel_source(path)
    for line_no, line in enumerate(text.splitlines(), start=1):
        raw = line.strip()
        if not raw:
            continue

        # V1: [TIME][DEVICE][TEST][RESULT]
        m = v1_re.match(raw)
        if m:
            timestamp, device_id, test_name, result = [x.strip() for x in m.groups()]
            status = normalize_status(result)
            if status is None:
                warnings.append({
                    'source_file': source,
                    'line_number': line_no,
                    'line': line,
                    'warning': f'Unknown status for V1 line: {result}'
                })
                continue
            records.append({
                'timestamp': timestamp,
                'device_id': device_id,
                'test_name': test_name,
                'status': status,
                'source_file': source,
                'format_version': 'V1'
            })
            continue

        # V2: JSON line with ts, dut, case, result
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            obj = None
        if isinstance(obj, dict) and all(k in obj for k in ('ts', 'dut', 'case', 'result')):
            status = normalize_status(obj.get('result'))
            if status is None:
                warnings.append({
                    'source_file': source,
                    'line_number': line_no,
                    'line': line,
                    'warning': f'Unknown status for V2 line: {obj.get("result")}'
                })
                continue
            records.append({
                'timestamp': str(obj.get('ts')),
                'device_id': str(obj.get('dut')),
                'test_name': str(obj.get('case')),
                'status': status,
                'source_file': source,
                'format_version': 'V2'
            })
            continue

        warnings.append({
            'source_file': source,
            'line_number': line_no,
            'line': line,
            'warning': 'Unknown log format'
        })

unified_path = OUTPUT_DIR / 'unified.json'
warnings_path = OUTPUT_DIR / 'warnings.json'
unified_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

print('Wrote', unified_path, 'records', len(records))
print('Wrote', warnings_path, 'warnings', len(warnings))
print('Unified preview:')
print(json.dumps(records[:5], ensure_ascii=False, indent=2))
print('Warnings preview:')
print(json.dumps(warnings[:5], ensure_ascii=False, indent=2))

# Verification: reopen every output and confirm requirements.
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))

assert isinstance(loaded_records, list), 'unified.json must be a JSON array'
assert isinstance(loaded_warnings, list), 'warnings.json must be a JSON array'
assert len(loaded_records) == 6, f'expected 6 recognized rows, got {len(loaded_records)}'
assert len(loaded_warnings) == 2, f'expected 2 warning rows, got {len(loaded_warnings)}'
for idx, rec in enumerate(loaded_records, 1):
    assert list(rec.keys()) == required_fields, f'record {idx} field order/names mismatch: {list(rec.keys())}'
    assert rec['status'] in ('Pass', 'Fail'), f'record {idx} status not normalized: {rec["status"]}'
    assert rec['format_version'] in ('V1', 'V2'), f'record {idx} bad format_version: {rec["format_version"]}'
    for field in required_fields:
        assert isinstance(rec[field], str), f'record {idx} field {field} is not text'
for idx, warn in enumerate(loaded_warnings, 1):
    for field in ('source_file', 'line_number', 'line', 'warning'):
        assert field in warn, f'warning {idx} missing {field}'
    assert isinstance(warn['line_number'], int), f'warning {idx} line_number not integer'
    assert warn['warning'], f'warning {idx} empty warning'
print('CHECK PASSED: unified.json exists with 6 records and required fields; statuses are Pass/Fail; warnings.json exists with 2 unknown-format line warnings; input files were not modified.')
