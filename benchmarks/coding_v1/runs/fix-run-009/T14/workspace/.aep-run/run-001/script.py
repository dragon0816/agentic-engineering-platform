from pathlib import Path
import csv

workspace = Path.cwd()
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('Workspace:', workspace)
print('Input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, p.stat().st_size, 'bytes')

csv_path = input_dir / 'large_results.csv'
print('\nInspecting:', csv_path)
with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    headers = next(reader)
    print('Headers:', headers)
    print('Sample rows:')
    for i, row in zip(range(5), reader):
        print(row)
