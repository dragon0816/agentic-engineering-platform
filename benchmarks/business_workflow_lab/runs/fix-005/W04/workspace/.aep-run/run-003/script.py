from pathlib import Path
import csv
p=Path('output/downloads/open_orders_2026_09.csv')
print('exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
with open(p, newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('headers', rows[0].keys() if rows else [])
print('row_count', len(rows))
print('order_ids', [r['OrderID'] for r in rows])
for r in rows[:3]: print(r)