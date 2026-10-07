from pathlib import Path
import csv

ws = Path.cwd()
print('Workspace:', ws)
print('Input files:')
for p in sorted((ws/'input').iterdir()):
    print(' -', p.name, p.stat().st_size, 'bytes')

csv_path = ws/'input'/'input.csv'
print('\ninput.csv exists:', csv_path.exists())
if csv_path.exists():
    with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = []
        for i, row in enumerate(reader):
            rows.append(row)
            if i >= 5:
                break
    print('CSV first rows:')
    for row in rows:
        print(row)

for name in ['DEPENDENCIES.txt', 'export.py']:
    p = ws/'input'/name
    print(f'\n{name} exists:', p.exists())
    if p.exists():
        txt = p.read_text(encoding='utf-8', errors='replace')
        print(txt[:2000])