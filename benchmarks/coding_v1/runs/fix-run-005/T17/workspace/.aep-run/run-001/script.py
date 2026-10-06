from pathlib import Path
import json
ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').rglob('*')):
    if p.is_file():
        print('-', p.relative_to(ws), 'size', p.stat().st_size)
fp = ws/'input'/'testplan.json'
print('testplan exists:', fp.exists())
if fp.exists():
    text = fp.read_text(encoding='utf-8')
    print('first 1000 chars:')
    print(text[:1000])
    data = json.loads(text)
    print('top-level type:', type(data).__name__)
    if isinstance(data, dict):
        print('top-level keys:', list(data.keys())[:20])
    elif isinstance(data, list):
        print('top-level list length:', len(data))
