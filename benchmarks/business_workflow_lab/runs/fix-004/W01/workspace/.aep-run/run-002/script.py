from pathlib import Path
import csv
p=Path('output/downloads/september_open_orders_raw.csv')
print('exists', p.exists(), p)
with open(p, newline='', encoding='utf-8-sig') as f:
    r=csv.reader(f)
    rows=list(r)
print('rows incl header', len(rows))
for row in rows[:20]: print(row)