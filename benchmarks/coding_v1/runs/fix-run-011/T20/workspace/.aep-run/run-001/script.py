from pathlib import Path
import csv, json
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
print('\nOUTPUT EXISTS:', (ws/'output').exists())

sop = ws/'input'/'supplied_sop.md'
if sop.exists():
    print('\n=== supplied_sop.md ===')
    print(sop.read_text(encoding='utf-8', errors='replace'))
else:
    print('\nNO supplied_sop.md found')

print('\n=== CSV previews ===')
for p in sorted((ws/'input').glob('*.csv')):
    print('\nCSV:', p.name)
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        for i, row in zip(range(6), reader):
            print(i, row)
