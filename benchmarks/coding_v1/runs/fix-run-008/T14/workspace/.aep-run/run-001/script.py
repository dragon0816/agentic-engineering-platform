from pathlib import Path
import csv
workspace = Path.cwd()
print('Workspace:', workspace)
print('Input files:')
for p in sorted((workspace/'input').glob('*')):
    print(' -', p.name, p.stat().st_size, 'bytes')
csv_path = workspace/'input'/'large_results.csv'
print('CSV exists:', csv_path.exists())
if csv_path.exists():
    with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        headers = next(reader, [])
        print('Headers:', headers)
        print('Sample rows:')
        for i, row in zip(range(5), reader):
            print(row)
