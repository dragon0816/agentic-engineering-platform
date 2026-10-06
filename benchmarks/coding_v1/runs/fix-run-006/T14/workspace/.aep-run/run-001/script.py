from pathlib import Path
import csv
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:')
for p in sorted(input_dir.glob('*')):
    print('-', p.name, p.stat().st_size, 'bytes')

csv_path = input_dir / 'large_results.csv'
print('exists large_results.csv:', csv_path.exists())
if csv_path.exists():
    with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        header = next(reader, None)
        print('header:', header)
        for i, row in zip(range(5), reader):
            print(f'row {i+1}:', row)
