from pathlib import Path
import json, re

input_dir = Path('input')
output_dir = Path('output')
output_dir.mkdir(parents=True, exist_ok=True)

v1_re = re.compile(r'^\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]$')

status_map = {
    'PASS': 'Pass',
    'PASSED': 'Pass',
    'OK': 'Pass',
    'FAIL': 'Fail',
    'FAILED': 'Fail',
    'NG': 'Fail',
}

def normalize_status(value):
    if value is None:
        return None
    return status_map.get(str(value).strip().upper())

records = []
warnings = []

for path in sorted(input_dir.rglob('*')):
    if not path.is_file():
        continue
    try:
        lines = path.read_text(encoding='utf-8-sig').splitlines()
    except UnicodeDecodeError:
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    rel_source = path.relative_to(input_dir).as_posix()
    for line_no, line in enumerate(lines, start=1):
        raw = line.strip()
        if not raw:
            continue

        parsed = None
        warning_reason = None

        m = v1_re.match(raw)
        if m:
            ts, dut, test_case, result = [x.strip() for x in m.groups()]
            status = normalize_status(result)
            if status:
                parsed = {
                    'timestamp': ts,
                    'device_id': dut,
                    'test_name': test_case,
                    'status': status,
                    'source_file': rel_source,
                    'format_version': 'V1',
                }
            else:
                warning_reason = f'V1 line has unknown result value: {result!r}'
        else:
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                warning_reason = 'Line is neither V1 bracket format nor valid JSON V2'
            else:
                if isinstance(obj, dict) and all(k in obj for k in ('ts', 'dut', 'case', 'result')):
                    status = normalize_status(obj.get('result'))
                    if status:
                        parsed = {
                            'timestamp': str(obj.get('ts')),
                            'device_id': str(obj.get('dut')),
                            'test_name': str(obj.get('case')),
                            'status': status,
                            'source_file': rel_source,
                            'format_version': 'V2',
                        }
                    else:
                        warning_reason = f'V2 JSON line has unknown result value: {obj.get("result")!r}'
                else:
                    warning_reason = 'JSON line does not contain required V2 fields: ts, dut, case, result'

        if parsed is not None:
            records.append(parsed)
        else:
            warnings.append({
                'source_file': rel_source,
                'line_number': line_no,
                'line': raw,
                'warning': warning_reason or 'Unknown format',
            })

unified_path = output_dir / 'unified.json'
warnings_path = output_dir / 'warnings.json'
unified_path.write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

# Verification from saved outputs
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
required_keys = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']
assert isinstance(loaded_records, list)
assert isinstance(loaded_warnings, list)
assert all(list(r.keys()) == required_keys for r in loaded_records), 'unified keys/order mismatch'
assert all(r['status'] in ('Pass', 'Fail') for r in loaded_records), 'status not normalized'
assert all(r['format_version'] in ('V1', 'V2') for r in loaded_records), 'bad format version'
assert all(isinstance(r[k], str) for r in loaded_records for k in required_keys), 'unified values must be text strings'
assert len(loaded_records) == 6, f'expected 6 parsed records, got {len(loaded_records)}'
assert len(loaded_warnings) == 2, f'expected 2 warnings, got {len(loaded_warnings)}'
assert all(w['source_file'] == 'logs/run_c.log' for w in loaded_warnings), 'warnings should be from unknown-format run_c.log'

print('Wrote:', unified_path.as_posix(), 'records:', len(loaded_records))
print('Wrote:', warnings_path.as_posix(), 'warnings:', len(loaded_warnings))
print('Checked unified.json fields:', required_keys)
print('Checked status values are only Pass/Fail, format_version is V1/V2, record count is 6.')
print('Checked warnings.json records unknown-format lines, warning count is 2.')