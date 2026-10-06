from pathlib import Path
import csv
p=Path('output/downloads/september_open_orders_export.csv')
print('exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
with p.open(newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('rows', len(rows))
print('headers', rows[0].keys() if rows else [])
for r in rows:
    print(r)
