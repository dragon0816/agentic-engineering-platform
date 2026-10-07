from pathlib import Path
import json, hashlib, os

ws = Path.cwd()
input_dir = ws / 'input'
out_dir = ws / 'output'
data_path = out_dir / 'data.json'

print(f'workspace={ws}')
print(f'input_dir_exists={input_dir.exists()}')
print(f'output_dir_exists={out_dir.exists()}')

# Show relevant input files, but do not modify them.
input_files = sorted([p.relative_to(ws).as_posix() for p in input_dir.rglob('*') if p.is_file()]) if input_dir.exists() else []
print('input_files=' + json.dumps(input_files, ensure_ascii=False))

# Check output/data.json.
print(f'data_json_exists={data_path.exists()}')
if not data_path.exists():
    raise SystemExit('FAIL: output/data.json is missing')

raw = data_path.read_bytes()
print(f'data_json_bytes={len(raw)}')
print('data_json_sha256=' + hashlib.sha256(raw).hexdigest())
try:
    data = json.loads(raw.decode('utf-8'))
except Exception as e:
    raise SystemExit(f'FAIL: output/data.json is not valid UTF-8 JSON: {e}')

print('data_json_valid=True')
print('data_json_type=' + type(data).__name__)
if not isinstance(data, (dict, list)):
    raise SystemExit('FAIL: output/data.json JSON root is not object or array')

if isinstance(data, dict):
    print('data_json_keys=' + json.dumps(sorted(data.keys()), ensure_ascii=False))
    # Print a compact preview only.
    print('data_json_preview=' + json.dumps(data, ensure_ascii=False, sort_keys=True)[:500])
else:
    print(f'data_json_length={len(data)}')
    print('data_json_preview=' + json.dumps(data[:3], ensure_ascii=False, sort_keys=True)[:500])

# List all output files produced so far.
output_files = []
if out_dir.exists():
    for p in sorted(out_dir.rglob('*')):
        if p.is_file():
            output_files.append({'path': p.relative_to(ws).as_posix(), 'bytes': p.stat().st_size})
print('output_files=' + json.dumps(output_files, ensure_ascii=False))
print('check_completed=True')