from pathlib import Path
import csv

base = Path('.')
print('workspace:', base.resolve())
print('input files:')
for p in sorted((base/'input').iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)

for name in ['export.py', 'DEPENDENCIES.txt', 'input.csv']:
    p = base/'input'/name
    print('\n=== input/%s ===' % name)
    if not p.exists():
        print('MISSING')
        continue
    if name.endswith('.csv'):
        with p.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for i, row in zip(range(8), reader):
                print(i, row)
    else:
        text = p.read_text(encoding='utf-8', errors='replace')
        print(text[:4000])