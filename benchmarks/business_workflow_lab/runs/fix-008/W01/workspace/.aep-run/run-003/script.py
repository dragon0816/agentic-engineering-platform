from pathlib import Path
import csv
p=Path('output/downloads/sales_orders_2026-09-01_2026-09-30_Open.csv')
print(p.exists(), p)
with p.open(newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('headers', rows[0].keys() if rows else [])
print('count', len(rows))
for r in rows:
    print(r)