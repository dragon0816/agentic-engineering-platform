from pathlib import Path
import csv

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('workspace:', workspace)
print('input files:')
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
    print('sample row count read:', len(rows))
    if rows:
        print('headers:', rows[0])
        for idx, row in enumerate(rows[1:], start=1):
            print(f'sample row {idx}:', row)
