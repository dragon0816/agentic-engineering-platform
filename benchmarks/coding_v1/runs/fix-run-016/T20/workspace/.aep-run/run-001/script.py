from pathlib import Path
import csv
base = Path('.')
print('WORKSPACE', base.resolve())
print('INPUT FILES:')
for p in sorted((base/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
print('\nSOP:')
sop = base/'input'/'supplied_sop.md'
if sop.exists():
    print(sop.read_text(encoding='utf-8'))
else:
    print('supplied_sop.md not found')
print('\nCSV INSPECTION:')
for p in sorted((base/'input').glob('*.csv')):
    print('CSV', p.name)
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        sample = f.read(4096)
        print('first chars:', repr(sample[:300]))
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel
        reader = csv.DictReader(f, dialect=dialect)
        print('headers:', reader.fieldnames)
        for i, row in zip(range(5), reader):
            print('row', i+1, row)
