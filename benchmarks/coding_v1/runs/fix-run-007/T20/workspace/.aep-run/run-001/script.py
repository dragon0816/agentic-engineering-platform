from pathlib import Path
import csv, os
ws=Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
print('\nSOP supplied_sop.md:')
sop=ws/'input'/'supplied_sop.md'
if sop.exists():
    print(sop.read_text(encoding='utf-8', errors='replace'))
else:
    print('MISSING')
print('\nCSV samples:')
for p in sorted((ws/'input').glob('*.csv')):
    print('\nFILE', p.name)
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        reader=csv.reader(f)
        for i,row in zip(range(6), reader):
            print(i, row)
