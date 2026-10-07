from pathlib import Path
import json
base=Path('input')
print('Workspace:', Path.cwd())
print('Input files:')
for p in sorted(base.rglob('*')):
    if p.is_file():
        print('-', p.as_posix(), p.stat().st_size, 'bytes')
path=base/'testplan.json'
print('\nInspecting', path.as_posix())
text=path.read_text(encoding='utf-8')
print('First 1000 chars:')
print(text[:1000])
try:
    data=json.loads(text)
    print('JSON root type:', type(data).__name__)
    if isinstance(data, dict):
        print('Top-level keys:', list(data.keys())[:20])
    elif isinstance(data, list):
        print('Top-level length:', len(data))
except Exception as e:
    print('JSON parse error:', repr(e))