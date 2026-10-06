from pathlib import Path
import json
import re

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
output_dir.mkdir(parents=True, exist_ok=True)

v1_re = re.compile(r'^\s*\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\[([^\]]+)\]\s*$')

PASS_TOKENS = {'pass', 'passed', 'ok', 'success', 'succeed', 'true', '1'}
FAIL_TOKENS = {'fail', 'failed', 'ng', 'error', 'false', '0'}

def normalize_status(value):
    if value is None:
        return None
    s = str(value).strip()
    key = s.lower()
    if key in PASS_TOKENS:
        return 'Pass'
    if key in FAIL_TOKENS:
        return 'Fail'
    # tolerate common variants with extra punctuation/spacing
    compact = re.sub(r'[^a-z0-9]+', '', key)
    if compact in PASS_TOKENS:
        return 'Pass'
    if compact in FAIL_TOKENS:
        return 'Fail'
    return None

records = []
warnings = []

if not input_dir.exists():
    raise SystemExit(f'Input directory not found: {input_dir}')

files = sorted([p for p in input_dir.rglob('*') if p.is_file()])

for path in files:
    rel = path.relative_to(input_dir).as_posix()
    try:
        text = path.read_text(encoding='utf-8-sig')
    except UnicodeDecodeError:
        text = path.read_text(encoding='utf-8', errors='replace')
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        parsed = None
        fmt = None
        # Try V2 JSON line first, then V1 bracket format.
        try:
            obj = json.loads(line)
            if isinstance(obj, dict) and all(k in obj for k in ('ts', 'dut', 'case', 'result')):
                status = normalize_status(obj.get('result'))
                if status is None:
                    warnings.append({
                        'source_file': rel,
                        'line': line_no,
                        'warning': 'Unknown result/status value',
                        'content': line,
                    })
                    continue
                parsed = {
                    'timestamp': obj.get('ts'),
                    'device_id': obj.get('dut'),
                    'test_name': obj.get('case'),
                    'status': status,
                    'source_file': rel,
                    'format_version': 'V2',
                }
                fmt = 'V2'
            elif isinstance(obj, dict):
                warnings.append({
                    'source_file': rel,
                    'line': line_no,
                    'warning': 'JSON line missing required V2 fields ts, dut, case, result',
                    'content': line,
                })
                continue
        except json.JSONDecodeError:
            pass

        if parsed is None:
            m = v1_re.match(line)
            if m:
                ts, dut, case, result = [x.strip() for x in m.groups()]
                status = normalize_status(result)
                if status is None:
                    warnings.append({
                        'source_file': rel,
                        'line': line_no,
                        'warning': 'Unknown result/status value',
                        'content': line,
                    })
                    continue
                parsed = {
                    'timestamp': ts,
                    'device_id': dut,
                    'test_name': case,
                    'status': status,
                    'source_file': rel,
                    'format_version': 'V1',
                }
                fmt = 'V1'

        if parsed is None:
            warnings.append({
                'source_file': rel,
                'line': line_no,
                'warning': 'Unknown log format',
                'content': line,
            })
        else:
            records.append(parsed)

# Deterministic order: input file order and line order already preserved.
unified_path = output_dir / 'unified.json'
warnings_path = output_dir / 'warnings.json'
unified_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')
warnings_path.write_text(json.dumps(warnings, ensure_ascii=False, indent=2), encoding='utf-8')

print(f'Input files processed: {len(files)}')
for p in files:
    print(f'- {p.relative_to(input_dir).as_posix()}')
print(f'Records written: {len(records)} -> {unified_path}')
print(f'Warnings written: {len(warnings)} -> {warnings_path}')
if warnings:
    print('Warnings preview:')
    for w in warnings[:10]:
        print(json.dumps(w, ensure_ascii=False))
