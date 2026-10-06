import csv
from pathlib import Path
p=Path('output/downloads/sept_open_orders.csv')
with open(p, newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('count', len(rows))
print('ids', [r['OrderID'] for r in rows])