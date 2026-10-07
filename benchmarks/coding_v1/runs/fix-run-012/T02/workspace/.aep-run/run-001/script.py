from pathlib import Path
import csv

workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:', [p.name for p in input_dir.iterdir() if p.is_file()])
path = input_dir / 'results.csv'
print('results.csv exists:', path.exists())
with path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    rows = []
    for i, row in enumerate(reader):
        rows.append(row)
        if i >= 5:
            break
print('sample rows:')
for i, row in enumerate(rows):
    print(i, row)
if rows:
    print('headers:', rows[0])
    print('column count:', len(rows[0]))