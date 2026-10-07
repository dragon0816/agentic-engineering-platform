import os, csv, json
from pathlib import Path
ws=Path.cwd()
print('workspace', ws)
for sub in ['input','output']:
    p=ws/sub
    print(sub, 'exists=', p.exists())
    if p.exists():
        for f in sorted(p.iterdir()):
            print(sub, f.name, 'size', f.stat().st_size)
# print SOP and CSV headers/sample rows
for name in ['supplied_sop.md']:
    p=ws/'input'/name
    print('\n---', p, '---')
    if p.exists():
        print(p.read_text(encoding='utf-8'))

for p in sorted((ws/'input').glob('*.csv')):
    print('\n--- CSV', p.name, '---')
    with p.open('r', encoding='utf-8-sig', newline='') as fh:
        reader=csv.DictReader(fh)
        print('headers=', reader.fieldnames)
        for i,row in zip(range(5), reader):
            print('row', i+1, row)
