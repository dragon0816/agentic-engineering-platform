import os, json
from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
for root, dirs, files in os.walk(ws/'input'):
    level = Path(root).relative_to(ws/'input').parts
    indent = '  ' * len(level)
    print(f'{indent}{Path(root).name}/')
    for f in files:
        p = Path(root)/f
        print(f'{indent}  {f} ({p.stat().st_size} bytes)')

p = ws/'input'/'testplan.json'
print('\nReading:', p)
text = p.read_text(encoding='utf-8')
print('First 1000 chars:')
print(text[:1000])
try:
    data = json.loads(text)
    print('\nTop-level type:', type(data).__name__)
    if isinstance(data, dict):
        print('Top-level keys:', list(data.keys())[:20])
    elif isinstance(data, list):
        print('Top-level list length:', len(data))
        print('First item type:', type(data[0]).__name__ if data else None)
except Exception as e:
    print('JSON parse error:', repr(e))