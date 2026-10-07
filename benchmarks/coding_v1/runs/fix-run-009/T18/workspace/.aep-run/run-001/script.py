from pathlib import Path
import csv

ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES')
for p in sorted((ws/'input').iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)

csv_path = ws/'input'/'input.csv'
print('\nCSV INSPECTION:', csv_path)
with csv_path.open(newline='', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    rows = list(reader)
print('rows including header:', len(rows))
print('header:', rows[0] if rows else None)
print('sample rows:', rows[1:6])

print('\nDEPENDENCIES.txt')
dep = ws/'input'/'DEPENDENCIES.txt'
print(dep.read_text(encoding='utf-8', errors='replace'))

print('\nOriginal export.py first 240 lines')
orig = ws/'input'/'export.py'
text = orig.read_text(encoding='utf-8', errors='replace')
for i, line in enumerate(text.splitlines()[:240], 1):
    print(f'{i:03d}: {line}')