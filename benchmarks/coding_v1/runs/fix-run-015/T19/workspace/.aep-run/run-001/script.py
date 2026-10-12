from pathlib import Path
import csv

workspace = Path.cwd()
input_dir = workspace / 'input'
print('Workspace:', workspace)
print('Input files:', [p.name for p in sorted(input_dir.iterdir())])
path = input_dir / 'mixed.csv'
print('mixed.csv exists:', path.exists())
if path.exists():
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        rows = []
        for i, row in enumerate(reader):
            rows.append(row)
            if i >= 5:
                break
    print('First rows parsed by csv module:')
    for i, row in enumerate(rows):
        print(i, row)
    if rows:
        print('Header count:', len(rows[0]))
        print('Headers:', rows[0])
