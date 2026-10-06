from pathlib import Path
import csv
p=Path('output/downloads/orders_sep2026_open.csv')
print('exists', p.exists(), p, p.stat().st_size if p.exists() else None)
with open(p, newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('rows', len(rows))
print('headers', rows[0].keys() if rows else [])
for r in rows: print(r)