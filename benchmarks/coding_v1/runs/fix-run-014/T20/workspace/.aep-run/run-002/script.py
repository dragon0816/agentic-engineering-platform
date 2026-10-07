from pathlib import Path
import csv, json
print('--- input/supplied_sop.md ---')
print(Path('input/supplied_sop.md').read_text(encoding='utf-8', errors='replace'))
print('\n--- manifest.json ---')
print(Path('input/manifest.json').read_text(encoding='utf-8', errors='replace'))
print('\n--- CSV samples ---')
for csv_path in sorted(Path('input').rglob('*.csv')):
    print('CSV', csv_path)
    with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader=csv.reader(f)
        for i,row in zip(range(10), reader):
            print(i, row)
    print()