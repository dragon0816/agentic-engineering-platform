from pathlib import Path
import csv
p=Path('output/downloads/orders_2026-09_open.csv')
print('exists', p.exists(), p)
with open(p, newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('headers', rows[0].keys() if rows else [])
print('row_count', len(rows))
for r in rows:
    print(r)