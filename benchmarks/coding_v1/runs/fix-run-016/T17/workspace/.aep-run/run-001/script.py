from pathlib import Path
import json
workspace = Path.cwd()
print('cwd:', workspace)
print('input files:')
for p in sorted((workspace/'input').rglob('*')):
    print(' -', p.relative_to(workspace), 'size=', p.stat().st_size if p.is_file() else 'DIR')
path = workspace/'input'/'testplan.json'
print('testplan exists:', path.exists())
if path.exists():
    text = path.read_text(encoding='utf-8')
    print('first 1000 chars:')
    print(text[:1000])
    try:
        data=json.loads(text)
        print('top-level type:', type(data).__name__)
        if isinstance(data, dict):
            print('top-level keys:', list(data.keys()))
        elif isinstance(data, list):
            print('top-level length:', len(data))
    except Exception as e:
        print('json parse error:', repr(e))