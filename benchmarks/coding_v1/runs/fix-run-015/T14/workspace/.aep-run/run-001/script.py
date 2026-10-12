from pathlib import Path
import csv

ws = Path.cwd()
print('workspace=', ws)
input_dir = ws / 'input'
output_dir = ws / 'output'
print('input files:')
for p in sorted(input_dir.glob('*')):
    print(' -', p.name, 'size=', p.stat().st_size)

csv_path = input_dir / 'large_results.csv'
print('target exists=', csv_path.exists())
with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader, None)
    print('headers=', header)
    for i, row in zip(range(5), reader):
        print('sample', i+1, '=', row)
