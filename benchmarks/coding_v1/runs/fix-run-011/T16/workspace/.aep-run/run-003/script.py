from pathlib import Path
import json
import re

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)
unified_path = output_dir / 'unified.json'
warnings_path = output_dir / 'warnings.json'

v1_re = re.compile(r'^\[(?P<timestamp>[^\]]+)\]\[(?P<device_id>[^\]]+)\]\[(?P<test_name>[^\]]+)\]\[(?P<status>[^\]]+)\]\s*$')

def normalize_status(value):
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {'pass', 'passed', 'ok', 'success'}:
        return 'Pass'
    if s in {'fail', 'failed', 'ng', 'error'}:
        return 'Fail'
    return None

def rel_source(path):
    return path.relative_to(input_dir).as_posix()

records = []
warnings = []
files = [p for p in sorted(input_dir.rglob('*')) if p.is_file()]

for path in files:
    with path.open('r', encoding='utf-8-sig', errors='replace') as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.rstrip('\n\r')
            if not line.strip():
                warnings.append({
                    'source_file': rel_source(path),
                    'line_number': line_no,
                    'line': line,
                    'warning': 'blank line'
                })
                continue

            parsed = None
            fmt = None

            # V1: [TIME][DEVICE][TEST][RESULT]
            m = v1_re.match(line)
            if m:
                parsed = m.groupdict()
                fmt = 'V1'
            else:
                # V2: each line JSON with ts, dut, case, result
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    obj = None
                if isinstance(obj, dict) and all(k in obj for k in ('ts', 'dut', 'case', 'result')):
                    parsed = {
                        'timestamp': obj.get('ts'),
                        'device_id': obj.get('dut'),
                        'test_name': obj.get('case'),
                        'status': obj.get('result')
                    }
                    fmt = 'V2'

            if parsed is None:
                warnings.append({
                    'source_file': rel_source(path),
                    'line_number': line_no,
                    'line': line,
                    'warning': 'unknown format'
                })
                continue

            status = normalize_status(parsed.get('status'))
            if status is None:
                warnings.append({
                    'source_file': rel_source(path),
                    'line_number': line_no,
                    'line': line,
                    'warning': f"unknown status: {parsed.get('status')!r}"
                })
                continue

            records.append({
                'timestamp': str(parsed.get('timestamp')),
                'device_id': str(parsed.get('device_id')),
                'test_name': str(parsed.get('test_name')),
                'status': status,
                'source_file': rel_source(path),
                'format_version': fmt
            })

with unified_path.open('w', encoding='utf-8') as f:
    json.dump(records, f, ensure_ascii=False, indent=2)
    f.write('\n')

with warnings_path.open('w', encoding='utf-8') as f:
    json.dump(warnings, f, ensure_ascii=False, indent=2)
    f.write('\n')

# Reopen and verify stated requirements.
with unified_path.open('r', encoding='utf-8') as f:
    loaded_records = json.load(f)
with warnings_path.open('r', encoding='utf-8') as f:
    loaded_warnings = json.load(f)

expected_cols = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']
assert isinstance(loaded_records, list), 'unified.json is not a JSON array'
assert all(list(r.keys()) == expected_cols for r in loaded_records), 'unified fields/order mismatch'
assert all(r['status'] in {'Pass', 'Fail'} for r in loaded_records), 'status not normalized to Pass/Fail'
assert all(r['format_version'] in {'V1', 'V2'} for r in loaded_records), 'unexpected format_version'
assert isinstance(loaded_warnings, list), 'warnings.json is not a JSON array'
assert all('warning' in w and 'line' in w and 'source_file' in w and 'line_number' in w for w in loaded_warnings), 'warning fields missing'

from collections import Counter
print('Input files:', [str(p.relative_to(input_dir)) for p in files])
print('Wrote:', unified_path.relative_to(workspace), 'records=', len(loaded_records))
print('Wrote:', warnings_path.relative_to(workspace), 'warnings=', len(loaded_warnings))
print('Records by format:', dict(Counter(r['format_version'] for r in loaded_records)))
print('Records by status:', dict(Counter(r['status'] for r in loaded_records)))
print('Warning preview:', loaded_warnings[:3])
print('Verification passed: unified.json fields, status normalization, format versions, and warning entries checked.')