from pathlib import Path
import csv, json
base = Path('.')
print('Workspace:', base.resolve())
print('Input files:')
for p in sorted((base/'input').rglob('*')):
    print(' -', p.as_posix(), 'dir' if p.is_dir() else f'file {p.stat().st_size} bytes')

sop = base/'input'/'supplied_sop.md'
print('\n--- supplied_sop.md ---')
print(sop.read_text(encoding='utf-8'))

manifest = base/'input'/'manifest.json'
if manifest.exists():
    print('\n--- manifest.json ---')
    print(manifest.read_text(encoding='utf-8'))

csv_path = base/'input'/'data'/'test_results.csv'
print('\n--- CSV header/sample ---')
with csv_path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.DictReader(f)
    print('fieldnames:', reader.fieldnames)
    for i, row in enumerate(reader):
        print(i+1, row)
        if i >= 9:
            break