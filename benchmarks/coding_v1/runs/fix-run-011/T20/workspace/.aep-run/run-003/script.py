from pathlib import Path
import csv, os
root=Path('.')
print('WORKSPACE', root.resolve())
for p in sorted(root.rglob('*')):
    if p.is_file():
        print('FILE', p.as_posix(), 'size', p.stat().st_size)
print('\n--- supplied_sop.md ---')
sop=Path('supplied_sop.md')
if sop.exists():
    print(sop.read_text(encoding='utf-8'))
else:
    print('MISSING supplied_sop.md')
print('\n--- CSV previews ---')
for p in sorted(Path('input').glob('*.csv')):
    print('\nCSV', p.as_posix())
    with p.open(newline='', encoding='utf-8-sig') as f:
        reader=csv.reader(f)
        for i,row in zip(range(6), reader):
            print(i, row)
