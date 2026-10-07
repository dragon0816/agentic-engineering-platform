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
    headers = next(reader)
    print('headers:', headers)
    for i, row in zip(range(5), reader):
        print(f'sample row {i+1}:', row)
