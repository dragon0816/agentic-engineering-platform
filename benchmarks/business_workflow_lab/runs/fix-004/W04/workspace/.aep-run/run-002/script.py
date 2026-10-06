from pathlib import Path
import csv
p=Path('output/downloads/sept_open_orders.csv')
print('exists', p.exists(), p)
with p.open(encoding='utf-8-sig', newline='') as f:
    rows=list(csv.DictReader(f))
print('rows', len(rows))
print('headers', rows[0].keys() if rows else None)
for r in rows: print(r)