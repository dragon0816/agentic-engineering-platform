from pathlib import Path
import csv

ws = Path.cwd()
input_dir = ws / 'input'
print('WORKSPACE:', ws)
print('INPUT FILES:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)

csv_path = input_dir / 'mixed.csv'
print('mixed.csv exists:', csv_path.exists())
if csv_path.exists():
    with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        rows = []
        for i, row in enumerate(reader):
            rows.append(row)
            if i >= 5:
                break
    print('Sample rows read via csv module (utf-8-sig, quoted commas/newlines supported):')
    for i, row in enumerate(rows):
        print(i, row)
    if rows:
        print('Headers:', rows[0])
        print('Header count:', len(rows[0]))