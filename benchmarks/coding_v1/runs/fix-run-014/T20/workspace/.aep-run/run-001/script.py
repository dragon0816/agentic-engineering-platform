from pathlib import Path
import csv
base=Path('.')
print('workspace', base.resolve())
for p in sorted(base.rglob('*')):
    rel=p.relative_to(base)
    if p.is_file():
        print('FILE', rel, 'size', p.stat().st_size)
print('\n--- supplied_sop.md ---')
sop=Path('supplied_sop.md')
if sop.exists():
    print(sop.read_text(encoding='utf-8', errors='replace'))
else:
    print('MISSING supplied_sop.md')
print('\n--- input CSV samples ---')
for csv_path in sorted(Path('input').glob('*.csv')):
    print('CSV', csv_path)
    with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader=csv.reader(f)
        for i,row in zip(range(6), reader):
            print(i, row)
    print()