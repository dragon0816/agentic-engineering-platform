from pathlib import Path
import csv
ws=Path.cwd()
p=ws/'output'/'downloads'/'invoices_2026-09.csv'
print('download exists', p.exists(), p.stat().st_size)
with open(p, newline='', encoding='utf-8-sig') as f:
    r=csv.DictReader(f)
    print('headers', r.fieldnames)
    rows=list(r)
print('rows', len(rows))
for row in rows:
    print(row)