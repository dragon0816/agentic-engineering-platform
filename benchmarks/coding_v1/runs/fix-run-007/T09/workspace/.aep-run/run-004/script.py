from pathlib import Path
import json

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('workspace:', workspace)
print('input files:', sorted(p.name for p in input_dir.iterdir()) if input_dir.exists() else 'MISSING')
print('output files:', sorted(p.name for p in output_dir.iterdir()) if output_dir.exists() else 'MISSING')

required = output_dir / 'data.json'
print('data.json exists:', required.exists())
if required.exists():
    raw = required.read_text(encoding='utf-8')
    print('data.json bytes:', required.stat().st_size)
    try:
        data = json.loads(raw)
        print('data.json valid_json:', True)
        print('data type:', type(data).__name__)
        if isinstance(data, dict):
            print('top-level keys:', sorted(data.keys()))
            print('items type:', type(data.get('items')).__name__ if 'items' in data else 'MISSING')
            if isinstance(data.get('items'), list):
                print('items count:', len(data['items']))
    except Exception as e:
        print('data.json valid_json:', False)
        print('json_error:', repr(e))

worker = output_dir / 't09_worker.py'
print('t09_worker.py exists:', worker.exists())
if worker.exists():
    print('t09_worker.py bytes:', worker.stat().st_size)
