from pathlib import Path
import csv, json
root=Path('.')
print('WORKSPACE', root.resolve())
print('\n--- manifest.json ---')
mp=Path('input/manifest.json')
print(mp.read_text(encoding='utf-8') if mp.exists() else 'MISSING')
print('\n--- supplied_sop.md ---')
for candidate in [Path('supplied_sop.md'), Path('input/supplied_sop.md')]:
    print('CHECK', candidate.as_posix(), 'exists=', candidate.exists())
    if candidate.exists():
        print(candidate.read_text(encoding='utf-8'))
print('\n--- CSV previews recursive under input ---')
for p in sorted(Path('input').rglob('*.csv')):
    print('\nCSV', p.as_posix())
    with p.open(newline='', encoding='utf-8-sig') as f:
        reader=csv.reader(f)
        for i,row in zip(range(10), reader):
            print(i, row)
