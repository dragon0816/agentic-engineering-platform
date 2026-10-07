import csv, os, json
from pathlib import Path
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace=', workspace)
print('input files:')
for p in sorted(input_dir.iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)

csv_path = input_dir / 'mixed.csv'
print('mixed.csv exists=', csv_path.exists())
with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    rows = []
    for i, row in enumerate(reader):
        rows.append(row)
        if i >= 5:
            break
print('sample rows read via csv module:')
for i, row in enumerate(rows):
    print(i, repr(row))
if rows:
    print('headers:', rows[0])
    print('column_count:', len(rows[0]))
    print('has Device ID:', 'Device ID' in rows[0])