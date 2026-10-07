from pathlib import Path
import csv
workspace = Path.cwd()
input_dir = workspace / 'input'
print('workspace:', workspace)
print('input files:', [p.name for p in input_dir.iterdir() if p.is_file()])
csv_path = input_dir / 'mixed.csv'
print('mixed.csv exists:', csv_path.exists())
if csv_path.exists():
    print('size bytes:', csv_path.stat().st_size)
    with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        for i, row in enumerate(reader):
            print(f'row {i}:', row)
            if i >= 4:
                break