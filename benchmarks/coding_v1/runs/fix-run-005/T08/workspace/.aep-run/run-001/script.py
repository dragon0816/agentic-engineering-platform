from pathlib import Path
import json, csv
ws=Path('.')
input_dir=ws/'input'
print('Workspace:', ws.resolve())
print('Input files:')
for p in sorted(input_dir.iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
    text=p.read_text(encoding='utf-8-sig', errors='replace')
    print('  first 800 chars:')
    print(text[:800].replace('\r','\\r'))
    print('---')
