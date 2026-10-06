from pathlib import Path
import csv
workspace = Path.cwd()
print('workspace:', workspace)
input_dir = workspace / 'input'
output_dir = workspace / 'output'
print('input files:', [p.name for p in input_dir.iterdir()])
path = input_dir / 'mixed.csv'
print('mixed.csv exists:', path.exists())
if path.exists():
    data = path.read_bytes()
    print('byte length:', len(data))
    print('starts with UTF-8 BOM:', data.startswith(b'\xef\xbb\xbf'))
    print('first 200 bytes:', data[:200])
    with path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        rows=[]
        for i,row in enumerate(reader):
            rows.append(row)
            if i >= 4:
                break
    print('sample rows count:', len(rows))
    for i,row in enumerate(rows):
        print(f'row {i}: fields={len(row)} values={row}')