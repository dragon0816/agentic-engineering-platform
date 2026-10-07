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
    reader = csv.DictReader(f)
    print('Headers:', reader.fieldnames)
    for i, row in enumerate(reader, start=1):
        print(f'Sample row {i}:', row)
        if i >= 5:
            break
