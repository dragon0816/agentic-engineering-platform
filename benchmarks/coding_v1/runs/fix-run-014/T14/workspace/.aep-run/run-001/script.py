from pathlib import Path
import csv

ws = Path.cwd()
input_dir = ws / 'input'
print('workspace:', ws)
print('input files:', [p.name for p in input_dir.iterdir()])
path = input_dir / 'large_results.csv'
print('large_results.csv exists:', path.exists())
with path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print('headers:', reader.fieldnames)
    for i, row in zip(range(5), reader):
        print('sample', i+1, row)
