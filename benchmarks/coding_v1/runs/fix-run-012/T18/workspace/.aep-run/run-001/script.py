from pathlib import Path
import csv

base = Path('.')
print('Workspace:', base.resolve())
print('Input files:')
for p in sorted((base/'input').iterdir()):
    print(' -', p, 'size=', p.stat().st_size)

csv_path = base/'input'/'input.csv'
print('\ninput.csv exists:', csv_path.exists())
if csv_path.exists():
    with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
    print('CSV row count including header:', len(rows))
    print('CSV header:', rows[0] if rows else None)
    print('CSV sample rows:', rows[1:6])

for name in ['export.py','DEPENDENCIES.txt']:
    p = base/'input'/name
    print(f'\n--- input/{name} exists: {p.exists()} ---')
    if p.exists():
        text = p.read_text(encoding='utf-8', errors='replace')
        print(text[:4000])
