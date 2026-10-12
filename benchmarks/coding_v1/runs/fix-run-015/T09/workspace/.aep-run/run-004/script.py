from pathlib import Path
import json

ws = Path.cwd()
input_dir = ws / 'input'
output_dir = ws / 'output'
print('workspace:', ws)
print('input files:', sorted(p.name for p in input_dir.iterdir()) if input_dir.exists() else 'missing input dir')
print('output files:', sorted(p.name for p in output_dir.iterdir()) if output_dir.exists() else 'missing output dir')

out = output_dir / 'data.json'
if not out.exists():
    raise SystemExit('FAIL: output/data.json does not exist')

raw = out.read_text(encoding='utf-8')
print('data.json bytes:', out.stat().st_size)
print('data.json text:', raw)

try:
    data = json.loads(raw)
except Exception as e:
    raise SystemExit(f'FAIL: data.json is not valid JSON: {e}')

print('data.json parsed type:', type(data).__name__)
if not isinstance(data, (dict, list)):
    raise SystemExit('FAIL: data.json JSON root is not an object or array')

# Check there was a platform-runtime result file produced by the approved workflow output path only; do not modify any inputs.
print('PASS: output/data.json exists and contains valid JSON')
