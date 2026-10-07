import json, os
from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:', sorted(p.name for p in input_dir.iterdir()))
path = input_dir / 'testplan.json'
print('testplan exists:', path.exists())
if path.exists():
    raw = path.read_text(encoding='utf-8')
    print('size bytes:', len(raw.encode('utf-8')))
    data = json.loads(raw)
    print('top type:', type(data).__name__)
    if isinstance(data, dict):
        print('top keys:', list(data.keys())[:20])
    elif isinstance(data, list):
        print('top list length:', len(data))
        print('first item type:', type(data[0]).__name__ if data else None)
    found=[]
    def walk(x, loc='$'):
        if isinstance(x, dict):
            if 'frequency' in x:
                found.append((loc, x.get('frequency'), type(x.get('frequency')).__name__, list(x.keys())))
            for k,v in x.items():
                walk(v, loc + '.' + str(k))
        elif isinstance(x, list):
            for i,v in enumerate(x[:50]):
                walk(v, f'{loc}[{i}]')
    walk(data)
    print('frequency fields found:', len(found))
    for row in found[:10]:
        print('sample frequency:', row)
