from pathlib import Path
import json

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('workspace:', workspace)
print('input exists:', input_dir.exists())
print('output exists:', output_dir.exists())
print('input files:')
for p in sorted(input_dir.rglob('*')):
    if p.is_file():
        print(' -', p.relative_to(workspace), 'size=', p.stat().st_size)

testplan = input_dir / 'testplan.json'
print('testplan exists:', testplan.exists())
if testplan.exists():
    text = testplan.read_text(encoding='utf-8')
    print('testplan bytes/chars:', testplan.stat().st_size, len(text))
    data = json.loads(text)
    print('root type:', type(data).__name__)
    if isinstance(data, dict):
        print('root keys:', list(data.keys()))
    elif isinstance(data, list):
        print('root length:', len(data))
    # Print a compact sample without altering anything
    sample = data[:2] if isinstance(data, list) else {k: data[k] for k in list(data.keys())[:5]} if isinstance(data, dict) else data
    print('sample:', json.dumps(sample, ensure_ascii=False, indent=2)[:2000])