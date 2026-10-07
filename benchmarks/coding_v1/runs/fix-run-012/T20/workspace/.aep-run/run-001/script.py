from pathlib import Path
import csv
base=Path('.')
print('workspace', base.resolve())
print('input files:')
for p in sorted((base/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
print('output exists:', (base/'output').exists())
# print SOP contents if present
for name in ['supplied_sop.md']:
    p=base/'input'/name
    if p.exists():
        print(f'\n===== {name} =====')
        print(p.read_text(encoding='utf-8'))
# CSV headers/sample
for p in sorted((base/'input').glob('*.csv')):
    print(f'\n===== CSV {p.name} =====')
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        reader=csv.reader(f)
        for i,row in zip(range(6), reader):
            print(i, row)
