from pathlib import Path
import csv, os
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
print('\nSOP supplied_sop.md:')
sop = ws/'input'/'supplied_sop.md'
if sop.exists():
    print(sop.read_text(encoding='utf-8'))
else:
    print('MISSING supplied_sop.md')
print('\nCSV previews:')
for p in sorted((ws/'input').glob('*.csv')):
    print(f'--- {p.name} ---')
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            print(row)
            if i >= 5:
                break