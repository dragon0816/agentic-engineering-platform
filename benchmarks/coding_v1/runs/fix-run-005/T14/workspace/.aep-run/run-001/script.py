from pathlib import Path
import csv
workspace=Path.cwd()
input_dir=workspace/'input'
print('workspace:', workspace)
print('input files:', [p.name for p in input_dir.iterdir()])
path=input_dir/'large_results.csv'
print('exists large_results.csv:', path.exists(), 'size:', path.stat().st_size if path.exists() else None)
with path.open('r', encoding='utf-8-sig', newline='') as f:
    reader=csv.reader(f)
    header=next(reader)
    print('headers:', header)
    for i,row in zip(range(5), reader):
        print('row', i+1, row)
