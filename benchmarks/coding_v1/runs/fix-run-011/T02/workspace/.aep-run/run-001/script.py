from pathlib import Path
import csv

workspace = Path.cwd()
input_path = workspace / 'input' / 'results.csv'
print('workspace:', workspace)
print('input exists:', input_path.exists())
print('input file:', input_path)
with input_path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    rows = []
    for i, row in enumerate(reader):
        rows.append(row)
        if i >= 5:
            break
print('sample rows including header:')
for row in rows:
    print(row)
if rows:
    print('headers:', rows[0])
    print('column count:', len(rows[0]))