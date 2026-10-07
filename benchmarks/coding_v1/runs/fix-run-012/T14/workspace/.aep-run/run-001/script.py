from pathlib import Path
import csv
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, p.stat().st_size, 'bytes')

csv_path = input_dir / 'large_results.csv'
print('\nInspecting:', csv_path)
with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    headers = next(reader)
    print('headers:', headers)
    for i, row in zip(range(5), reader):
        print(f'sample row {i+1}:', row)
