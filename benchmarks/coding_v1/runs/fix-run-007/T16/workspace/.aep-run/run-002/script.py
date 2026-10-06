from pathlib import Path
import json, re
ws = Path.cwd()
print('workspace:', ws)
print('Recursive input inspection:')
for path in sorted((ws/'input').rglob('*')):
    if path.is_file():
        rel = path.relative_to(ws/'input')
        print(f'--- {rel.as_posix()} size={path.stat().st_size}')
        try:
            text = path.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            text = path.read_text(encoding='utf-8-sig')
        lines = text.splitlines()
        print('line_count:', len(lines))
        for i, line in enumerate(lines[:5], 1):
            print(f'{i}: {line[:300]}')

# Processing script
input_dir = ws / 'input'
output_dir = ws / 'output'
output_dir.mkdir(exist_ok=True)

v1_re = re.compile(r'^\[(?P<timestamp>[^\]]+)\]\[(?P<device_id>[^\]]+)\]\[(?P<test_name>[^\]]+)\]\[(?P<status>[^\]]+)\]$')

def normalize_status(value):
    if value is None:
        return None
    s = str(value).strip().lower()
    if s in {'pass', 'passed', 'ok', 'success'}:
        return 'Pass'
    if s in {'fail', 'failed', 'ng', 'error'}:
        return 'Fail'
    return None

records = []
warnings = []

def add_warning(path, line_no, line, reason):
    warnings.append({
        'source_file': path.relative_to(input_dir).as_posix(),
        'line_number': line_no,
        'line': line,
        'warning': reason,
    })

for path in sorted(input_dir.rglob('*')):
    if not path.is_file():
        continue
    try:
        text = path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        text = path.read_text(encoding='utf-8-sig')
    rel_source = path.relative_to(input_dir).as_posix()
    for line_no, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line:
            add_warning(path, line_no, raw_line, 'empty line / unknown format')
            continue

        m = v1_re.match(line)
        if m:
            status = normalize_status(m.group('status'))
            if status is None:
                add_warning(path, line_no, raw_line, f"unrecognized status for V1: {m.group('status')}")
                continue
            records.append({
                'timestamp': m.group('timestamp'),
                'device_id': m.group('device_id'),
                'test_name': m.group('test_name'),
                'status': status,
                'source_file': rel_source,
                'format_version': 'V1',
            })
            continue

        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            add_warning(path, line_no, raw_line, f'unknown format: not V1 and invalid JSON ({e.msg})')
            continue

        if not isinstance(obj, dict):
            add_warning(path, line_no, raw_line, 'unknown format: JSON line is not an object')
            continue
        required = ['ts', 'dut', 'case', 'result']
        missing = [k for k in required if k not in obj]
        if missing:
            add_warning(path, line_no, raw_line, f"unknown format: V2 JSON missing fields {missing}")
            continue
        status = normalize_status(obj.get('result'))
        if status is None:
            add_warning(path, line_no, raw_line, f"unrecognized status for V2: {obj.get('result')}")
            continue
        records.append({
            'timestamp': obj.get('ts'),
            'device_id': obj.get('dut'),
            'test_name': obj.get('case'),
            'status': status,
            'source_file': rel_source,
            'format_version': 'V2',
        })

unified_path = output_dir / 'unified.json'
warnings_path = output_dir / 'warnings.json'
unified_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')

print('\nWrote outputs:')
print(unified_path, 'records=', len(records))
print(warnings_path, 'warnings=', len(warnings))
print('By format:', {v: sum(1 for r in records if r['format_version']==v) for v in ['V1','V2']})
print('Statuses:', {v: sum(1 for r in records if r['status']==v) for v in ['Pass','Fail']})

# Verification: reopen every output file and confirm stated requirements
loaded_records = json.loads(unified_path.read_text(encoding='utf-8'))
loaded_warnings = json.loads(warnings_path.read_text(encoding='utf-8'))
assert isinstance(loaded_records, list), 'unified.json must be a JSON array'
expected_keys = ['timestamp','device_id','test_name','status','source_file','format_version']
for i, rec in enumerate(loaded_records):
    assert list(rec.keys()) == expected_keys, f'record {i} columns mismatch: {list(rec.keys())}'
    assert rec['status'] in {'Pass','Fail'}, f'record {i} status not normalized: {rec["status"]}'
    assert rec['format_version'] in {'V1','V2'}, f'record {i} bad format_version: {rec["format_version"]}'
    assert isinstance(rec['source_file'], str) and rec['source_file'], f'record {i} missing source_file'
for i, warn in enumerate(loaded_warnings):
    for key in ['source_file','line_number','line','warning']:
        assert key in warn, f'warning {i} missing {key}'
    assert isinstance(warn['line_number'], int), f'warning {i} line_number not int'
print('\nVerification passed:')
print('- unified.json exists and is a JSON array')
print('- every unified record has exactly:', expected_keys)
print('- status values are only Pass/Fail')
print('- format_version values are only V1/V2')
print('- source_file is populated')
print('- warnings.json exists and warning records include source_file, line_number, line, warning')
print('- input files were only read; outputs are under output/')
