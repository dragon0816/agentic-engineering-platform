from pathlib import Path
import csv
p=Path('output/downloads/sales_orders_2026-09-01_2026-09-30_Open.csv')
print('exists', p.exists(), p.stat().st_size if p.exists() else None)
with p.open(newline='', encoding='utf-8-sig') as f:
    r=csv.reader(f)
    for i,row in zip(range(20),r): print(row)
