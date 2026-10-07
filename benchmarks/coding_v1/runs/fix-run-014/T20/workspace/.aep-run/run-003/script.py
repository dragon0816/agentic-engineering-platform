from pathlib import Path
import os, csv
base=Path('.')
print('Workspace:', base.resolve())
print('Input files:')
for p in sorted((base/'input').glob('*')):
    print(' -', p.name, 'size=', p.stat().st_size)
    if p.suffix.lower()=='.md':
        txt=p.read_text(encoding='utf-8', errors='replace')
        print('   MD first 1200 chars:\n', txt[:1200])
    elif p.suffix.lower()=='.csv':
        print('   CSV sample:')
        with p.open(newline='', encoding='utf-8-sig', errors='replace') as f:
            r=csv.reader(f)
            for i,row in zip(range(6), r): print('    ', row)
print('Output existing:')
for p in sorted((base/'output').glob('*')) if (base/'output').exists() else []:
    print(' -', p.name, 'size=', p.stat().st_size)
