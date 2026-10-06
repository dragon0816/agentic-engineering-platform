from pathlib import Path
import json
ws=Path.cwd()
print('workspace', ws)
print('input files:', [p.name for p in (ws/'input').iterdir()])
p=ws/'input'/'testplan.json'
print('testplan exists:', p.exists(), 'size:', p.stat().st_size if p.exists() else None)
if p.exists():
    text=p.read_text(encoding='utf-8')
    print('first 1000 chars:')
    print(text[:1000])
    data=json.loads(text)
    print('top-level type:', type(data).__name__)
    if isinstance(data, dict):
        print('top-level keys:', list(data.keys())[:20])
    elif isinstance(data, list):
        print('top-level length:', len(data))
