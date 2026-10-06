from pathlib import Path
import csv

workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, p.stat().st_size, 'bytes')

csv_path = input_dir / 'mixed.csv'
print('\nInspecting:', csv_path)
with open(csv_path, 'rb') as f:
    raw = f.read(200)
print('first bytes:', raw[:80])
print('has UTF-8 BOM:', raw.startswith(b'\xef\xbb\xbf'))

with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    rows = []
    for i, row in enumerate(reader):
        rows.append(row)
        if i >= 5:
            break
print('sample rows parsed with csv module:')
for i, row in enumerate(rows):
    print(i, repr(row))
if rows:
    print('headers:', rows[0])
    print('column count:', len(rows[0]))
