from pathlib import Path
import json
base=Path('input')
print('Input files:')
for p in sorted(base.rglob('*')):
    print(p, 'dir' if p.is_dir() else f'{p.stat().st_size} bytes')
path=base/'testplan.json'
print('\nReading', path)
text=path.read_text(encoding='utf-8')
print('First 1000 chars:')
print(text[:1000])
data=json.loads(text)
print('\nTop-level type:', type(data).__name__)
if isinstance(data, dict):
    print('Top-level keys:', list(data.keys()))
elif isinstance(data, list):
    print('Top-level length:', len(data))
    print('First item type:', type(data[0]).__name__ if data else None)
