from pathlib import Path
import csv
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:', [p.name for p in input_dir.iterdir() if p.is_file()])
csv_path = input_dir / 'mixed.csv'
print('mixed.csv exists:', csv_path.exists())
with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    rows = []
    for i, row in enumerate(reader):
        rows.append(row)
        if i >= 5:
            break
print('sample row count incl header:', len(rows))
if rows:
    print('headers:', rows[0])
    for idx, row in enumerate(rows[1:], start=1):
        print(f'sample row {idx}:', row)
