from pathlib import Path
import csv

ws = Path.cwd()
input_dir = ws / 'input'
print('workspace:', ws)
print('input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, p.stat().st_size, 'bytes')

csv_path = input_dir / 'large_results.csv'
print('exists large_results.csv:', csv_path.exists())
if csv_path.exists():
    with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        print('headers:', headers)
        for i, row in zip(range(5), reader):
            print(f'sample_row_{i+1}:', row)
