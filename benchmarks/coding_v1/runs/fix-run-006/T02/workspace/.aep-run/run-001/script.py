from pathlib import Path
import csv
workspace = Path.cwd()
input_dir = workspace/'input'
output_dir = workspace/'output'
print('Workspace:', workspace)
print('Input files:')
for p in sorted(input_dir.iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
path = input_dir/'results.csv'
print('\nReading sample from', path)
with path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    rows = []
    for i, row in enumerate(reader):
        rows.append(row)
        if i >= 5:
            break
for i, row in enumerate(rows):
    print(f'row {i}:', row)
if rows:
    print('Headers:', rows[0])
print('Output dir exists:', output_dir.exists())