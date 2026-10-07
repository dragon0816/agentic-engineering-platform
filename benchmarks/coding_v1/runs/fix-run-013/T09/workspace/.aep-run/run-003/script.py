from pathlib import Path
import json

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('Workspace:', workspace)
print('Input files:', sorted(p.name for p in input_dir.iterdir()) if input_dir.exists() else 'input dir missing')
print('Output files:', sorted(p.name for p in output_dir.iterdir()) if output_dir.exists() else 'output dir missing')

out = output_dir / 'data.json'
checks = {}
checks['data_json_exists'] = out.exists()
if out.exists():
    raw = out.read_text(encoding='utf-8')
    checks['data_json_bytes'] = out.stat().st_size
    try:
        data = json.loads(raw)
        checks['valid_json'] = True
        checks['top_level_type'] = type(data).__name__
        checks['keys'] = sorted(data.keys()) if isinstance(data, dict) else None
        print('data.json content:', json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True))
    except Exception as e:
        checks['valid_json'] = False
        checks['json_error'] = repr(e)
else:
    checks['valid_json'] = False
print('Checks:', json.dumps(checks, ensure_ascii=False, indent=2, sort_keys=True))

if not checks.get('data_json_exists') or not checks.get('valid_json'):
    raise SystemExit(1)
