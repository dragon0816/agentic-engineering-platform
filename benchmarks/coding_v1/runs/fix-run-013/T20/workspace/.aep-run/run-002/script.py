from pathlib import Path
import csv

workspace = Path.cwd()
print('workspace:', workspace)
print('input exists:', (workspace/'input').exists())
print('output exists:', (workspace/'output').exists())
print('\nInput tree:')
for p in sorted((workspace/'input').rglob('*')):
    print(' -', p.relative_to(workspace), 'dir' if p.is_dir() else f'file {p.stat().st_size} bytes')

sop = workspace/'input'/'supplied_sop.md'
print('\nSOP path:', sop, 'exists:', sop.exists())
if sop.exists():
    print('--- SOP START ---')
    print(sop.read_text(encoding='utf-8'))
    print('--- SOP END ---')

csvs = sorted((workspace/'input').rglob('*.csv'))
print('\nCSV files:', [str(p.relative_to(workspace)) for p in csvs])
for csv_path in csvs:
    print('\nCSV sample:', csv_path.relative_to(workspace))
    with csv_path.open('r', newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for i, row in zip(range(6), reader):
            print(i, row)
