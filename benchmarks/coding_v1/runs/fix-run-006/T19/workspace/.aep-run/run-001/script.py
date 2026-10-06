from pathlib import Path
import csv
workspace = Path.cwd()
print('workspace:', workspace)
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, p.stat().st_size, 'bytes')

csv_path = input_dir / 'mixed.csv'
print('\nInspecting:', csv_path)
with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
    sample = f.read(1000)
print('first 1000 chars repr:', repr(sample))
with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
    reader = csv.reader(f)
    for i, row in zip(range(5), reader):
        print(f'row {i}:', row)
