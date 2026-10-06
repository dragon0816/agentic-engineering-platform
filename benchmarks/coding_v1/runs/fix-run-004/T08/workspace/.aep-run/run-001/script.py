from pathlib import Path
import json, csv
base=Path('input')
print('Workspace input files:')
for p in sorted(base.rglob('*')):
    if p.is_file():
        print('-', p, 'size=', p.stat().st_size)
        data=p.read_text(encoding='utf-8-sig', errors='replace')
        print('--- sample start ---')
        print(data[:1000])
        print('--- sample end ---')
