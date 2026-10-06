from pathlib import Path
import csv
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
print('\nSUPPLIED_SOP.MD:')
sop = ws/'input'/'supplied_sop.md'
if sop.exists():
    print(sop.read_text(encoding='utf-8'))
else:
    print('MISSING input/supplied_sop.md')
print('\nCSV SAMPLES:')
for p in sorted((ws/'input').glob('*.csv')):
    print('CSV', p.name)
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        for i, row in zip(range(6), reader):
            print(i, row)
    print()