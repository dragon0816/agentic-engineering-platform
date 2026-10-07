from pathlib import Path
import csv, json
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT TREE')
for p in sorted((ws/'input').rglob('*')):
    print(' -', p.relative_to(ws), 'DIR' if p.is_dir() else f'FILE {p.stat().st_size} bytes')

sop = ws/'input'/'supplied_sop.md'
if sop.exists():
    print('\nSOP CONTENT START')
    print(sop.read_text(encoding='utf-8', errors='replace')[:4000])
    print('SOP CONTENT END')
else:
    print('NO SOP at input/supplied_sop.md')

print('\nCSV INSPECTION')
for csv_path in sorted((ws/'input').rglob('*.csv')):
    print('CSV', csv_path.relative_to(ws))
    with csv_path.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            print('  EMPTY')
            continue
        print('  header:', header)
        for i, row in zip(range(5), reader):
            print('  row', i+1, row)
