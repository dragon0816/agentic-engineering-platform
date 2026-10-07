from pathlib import Path
import csv

ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)

for name in ['DEPENDENCIES.txt', 'export.py']:
    p = ws/'input'/name
    print(f'\n===== input/{name} =====')
    if p.exists():
        print(p.read_text(encoding='utf-8', errors='replace'))
    else:
        print('MISSING')

csv_path = ws/'input'/'input.csv'
print('\n===== input/input.csv headers and sample =====')
with csv_path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print('headers:', reader.fieldnames)
    for i, row in zip(range(10), reader):
        print(i+1, row)
