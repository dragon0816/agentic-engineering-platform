from pathlib import Path
import csv

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('workspace:', workspace)
print('input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)

csv_path = input_dir / 'mixed.csv'
print('target exists:', csv_path.exists())
if csv_path.exists():
    raw = csv_path.read_bytes()[:32]
    print('first bytes:', raw)
    print('has UTF-8 BOM:', raw.startswith(b'\xef\xbb\xbf'))
    with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        for i, row in zip(range(6), reader):
            print(f'row {i}: columns={len(row)} values={row}')
print('output dir exists:', output_dir.exists())