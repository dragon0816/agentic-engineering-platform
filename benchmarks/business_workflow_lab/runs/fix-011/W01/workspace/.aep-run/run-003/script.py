from pathlib import Path
import csv
p=Path('output/downloads/sales_orders_2026-09-01_2026-09-30_Open.csv')
print('csv exists', p.exists(), p)
with p.open(encoding='utf-8-sig', newline='') as f:
    rows=list(csv.DictReader(f))
print('rows', len(rows))
print('headers', rows[0].keys() if rows else [])
for r in rows:
    print(r)
