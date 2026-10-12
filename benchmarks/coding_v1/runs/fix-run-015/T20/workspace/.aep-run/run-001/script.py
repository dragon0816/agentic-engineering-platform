from pathlib import Path
import csv
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)

sop = ws/'input'/'supplied_sop.md'
if sop.exists():
    print('\n--- supplied_sop.md ---')
    print(sop.read_text(encoding='utf-8'))
else:
    print('NO supplied_sop.md in input')

print('\n--- CSV samples ---')
for p in sorted((ws/'input').glob('*.csv')):
    print('\nCSV:', p.name)
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        for i, row in zip(range(6), reader):
            print(i, row)
