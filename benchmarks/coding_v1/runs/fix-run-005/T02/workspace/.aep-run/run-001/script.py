from pathlib import Path
import csv
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:', [p.name for p in input_dir.iterdir()])
path = input_dir / 'results.csv'
print('results.csv exists:', path.exists())
with path.open('r', encoding='utf-8-sig', newline='') as f:
    sample = f.read(2048)
print('first 2048 chars:')
print(sample)
with path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    rows = []
    for i, row in zip(range(6), reader):
        rows.append(row)
print('sample rows parsed:')
for r in rows:
    print(r)