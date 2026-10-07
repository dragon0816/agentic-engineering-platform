import json, os
from pathlib import Path
ws = Path.cwd()
inp = ws / 'input' / 'testplan.json'
out = ws / 'output'
print('workspace:', ws)
print('input exists:', inp.exists(), inp)
print('output exists:', out.exists(), out)
print('input files:')
for p in sorted((ws/'input').rglob('*')):
    print(' -', p.relative_to(ws), 'file' if p.is_file() else 'dir', p.stat().st_size if p.is_file() else '')
if inp.exists():
    text = inp.read_text(encoding='utf-8')
    print('testplan.json bytes:', len(text.encode('utf-8')))
    data = json.loads(text)
    print('root type:', type(data).__name__)
    if isinstance(data, dict):
        print('root keys:', list(data.keys())[:20])
    elif isinstance(data, list):
        print('root length:', len(data))
        print('first item type:', type(data[0]).__name__ if data else None)
    print('sample json:', json.dumps(data, ensure_ascii=False, indent=2)[:2000])