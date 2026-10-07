from pathlib import Path
import csv

workspace = Path.cwd()
input_dir = workspace / 'input'
print('Workspace:', workspace)
print('Input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)

csv_path = input_dir / 'results.csv'
print('\nReading:', csv_path)
with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    try:
        headers = next(reader)
    except StopIteration:
        headers = []
    print('Headers:', headers)
    print('Sample rows:')
    for i, row in zip(range(5), reader):
        print(i+1, row)
