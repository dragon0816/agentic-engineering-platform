from pathlib import Path
import csv
p=Path('output/downloads/sap_sales_orders_2026-09-01_2026-09-30_Open.csv')
print('exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
with open(p, newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('headers', rows[0].keys() if rows else [])
print('row_count', len(rows))
for r in rows[:20]: print(r)