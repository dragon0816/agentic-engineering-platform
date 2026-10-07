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

target = input_dir / 'testplan.json'
print('target exists:', target.exists())
if target.exists():
    text = target.read_text(encoding='utf-8')
    print('target first 1000 chars:')
    print(text[:1000])
    try:
        data = json.loads(text)
        print('json top type:', type(data).__name__)
        if isinstance(data, dict):
            print('top keys:', list(data.keys())[:20])
        elif isinstance(data, list):
            print('top list length:', len(data))
            print('first item type:', type(data[0]).__name__ if data else None)
    except Exception as e:
        print('json parse error:', repr(e))