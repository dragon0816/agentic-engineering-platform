from pathlib import Path
import json, re, os

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(exist_ok=True)

print('workspace:', workspace)
print('input tree:')
for p in sorted(input_dir.rglob('*')):
    rel = p.relative_to(input_dir)
    print(('DIR ' if p.is_dir() else 'FILE'), rel, 'size=', p.stat().st_size)
    if p.is_file():
        try:
            with p.open('r', encoding='utf-8-sig') as f:
                for i, line in zip(range(1, 4), f):
                    print(f'  sample {i}: {line.rstrip()}')
        except Exception as e:
            print('  sample read error:', repr(e))

v1_re = re.compile(r'^\[(?P<time>[^\]]+)\]\[(?P<device>[^\]]+)\]\[(?P<test>[^\]]+)\]\[(?P<result>[^\]]+)\]\s*$')

def normalize_status(value):
    s = str(value).strip().lower()
    if s in {'pass', 'passed', 'p', 'ok', 'success', 'true', '1'}:
        return 'Pass'
    if s in {'fail', 'failed', 'f', 'ng', 'error', 'false', '0'}:
        return 'Fail'
    return None

def read_text_lines(path):
    for enc in ('utf-8-sig', 'utf-8', 'cp950'):
        try:
            return path.read_text(encoding=enc).splitlines()
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding='utf-8', errors='replace').splitlines()

records = []
warnings = []
input_files = [p for p in sorted(input_dir.rglob('*')) if p.is_file()]
for path in input_files:
    rel = str(path.relative_to(input_dir)).replace('\\', '/')
    lines = read_text_lines(path)
    for line_no, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line:
            continue
        parsed = False
        # V2: one JSON object per line with fields ts, dut, case, result
        if line.startswith('{'):
            try:
                obj = json.loads(line)
                if isinstance(obj, dict) and all(k in obj for k in ('ts', 'dut', 'case', 'result')):
                    status = normalize_status(obj.get('result'))
                    if status is None:
                        warnings.append({
                            'source_file': rel,
                            'line_number': line_no,
                            'line': raw,
                            'warning': 'unrecognized status value',
                            'format_version': 'V2'
                        })
                    else:
                        records.append({
                            'timestamp': obj.get('ts'),
                            'device_id': obj.get('dut'),
                            'test_name': obj.get('case'),
                            'status': status,
                            'source_file': rel,
                            'format_version': 'V2'
                        })
                    parsed = True
            except json.JSONDecodeError:
                pass
        # V1: [TIME][DEVICE][TEST][RESULT]
        if not parsed:
            m = v1_re.match(line)
            if m:
                status = normalize_status(m.group('result'))
                if status is None:
                    warnings.append({
                        'source_file': rel,
                        'line_number': line_no,
                        'line': raw,
                        'warning': 'unrecognized status value',
                        'format_version': 'V1'
                    })
                else:
                    records.append({
                        'timestamp': m.group('time'),
                        'device_id': m.group('device'),
                        'test_name': m.group('test'),
                        'status': status,
                        'source_file': rel,
                        'format_version': 'V1'
                    })
                parsed = True
        if not parsed:
            warnings.append({
                'source_file': rel,
                'line_number': line_no,
                'line': raw,
                'warning': 'unknown format'
            })

unified_path = output_dir / 'unified.json'
warnings_path = output_dir / 'warnings.json'
unified_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')

# Verification: reopen outputs and confirm stated requirements.
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
required_cols = ['timestamp', 'device_id', 'test_name', 'status', 'source_file', 'format_version']
assert isinstance(loaded_records, list), 'unified.json must be a JSON array'
for idx, rec in enumerate(loaded_records):
    assert list(rec.keys()) == required_cols, f'record {idx} keys mismatch: {list(rec.keys())}'
    assert rec['status'] in ('Pass', 'Fail'), f'record {idx} status not normalized: {rec["status"]}'
    assert rec['format_version'] in ('V1', 'V2'), f'record {idx} format_version invalid: {rec["format_version"]}'
    assert isinstance(rec['source_file'], str) and rec['source_file'], f'record {idx} missing source_file'
assert isinstance(loaded_warnings, list), 'warnings.json must be a JSON array'
for idx, warn in enumerate(loaded_warnings):
    assert 'source_file' in warn and 'line_number' in warn and 'line' in warn and 'warning' in warn, f'warning {idx} missing fields'

print('\nWROTE:', unified_path)
print('WROTE:', warnings_path)
print('input file count:', len(input_files))
print('unified record count:', len(loaded_records))
print('warning count:', len(loaded_warnings))
print('status counts:', {s: sum(1 for r in loaded_records if r['status'] == s) for s in ['Pass','Fail']})
print('format counts:', {v: sum(1 for r in loaded_records if r['format_version'] == v) for v in ['V1','V2']})
print('verified unified columns:', required_cols)
print('verified statuses limited to Pass/Fail and warnings recorded separately')