from pathlib import Path
import json

workspace = Path.cwd()
input_dir = workspace / 'input'
print('Workspace:', workspace)
print('Input files:')
for p in sorted(input_dir.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(workspace), 'size=', p.stat().st_size)

path = input_dir / 'testplan.json'
print('\nReading:', path.relative_to(workspace))
with path.open('r', encoding='utf-8') as f:
    data = json.load(f)
print('Top-level type:', type(data).__name__)
if isinstance(data, dict):
    print('Top-level keys:', list(data.keys())[:20])
    print('Sample:', json.dumps({k: data[k] for k in list(data.keys())[:3]}, ensure_ascii=False, indent=2)[:2000])
elif isinstance(data, list):
    print('Top-level length:', len(data))
    print('First items sample:', json.dumps(data[:3], ensure_ascii=False, indent=2)[:2000])
else:
    print('Top-level value sample:', repr(data)[:500])