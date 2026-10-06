from pathlib import Path
import os, json, csv
ws=Path.cwd()
print('cwd', ws)
print('input files:')
for p in sorted((ws/'input').rglob('*')):
    print(p.relative_to(ws), 'dir' if p.is_dir() else f'{p.stat().st_size} bytes')
sop=ws/'input'/'supplied_sop.md'
if sop.exists():
    print('\n--- supplied_sop.md ---')
    print(sop.read_text(encoding='utf-8'))
print('\n--- CSV previews ---')
for p in sorted((ws/'input').glob('*.csv')):
    print('\nFILE', p.name)
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        reader=csv.reader(f)
        for i,row in zip(range(6), reader):
            print(i, row)
