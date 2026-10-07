from pathlib import Path
import csv
workspace = Path.cwd()
input_dir = workspace / 'input'
print('Workspace:', workspace)
print('Input files:', [p.name for p in input_dir.iterdir() if p.is_file()])
path = input_dir / 'results.csv'
print('results.csv exists:', path.exists())
with path.open('r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    rows = list(reader)
print('Total physical rows including header:', len(rows))
if rows:
    print('Headers:', rows[0])
    print('Sample rows:')
    for row in rows[1:6]:
        print(row)
