from pathlib import Path
import csv

base = Path('.')
print('WORKSPACE', base.resolve())
print('INPUT FILES:')
for p in sorted((base/'input').glob('*')):
    print(' -', p, 'size=', p.stat().st_size)

for rel in ['input/export.py', 'input/input.csv', 'input/DEPENDENCIES.txt']:
    p = base / rel
    print('\n====', rel, '====')
    if not p.exists():
        print('MISSING')
        continue
    if p.suffix.lower() == '.csv':
        with p.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = list(reader)
        print('row_count_including_header=', len(rows))
        print('headers=', rows[0] if rows else None)
        print('sample_rows=')
        for r in rows[1:8]:
            print(r)
    else:
        text = p.read_text(encoding='utf-8', errors='replace')
        print(text[:4000])
