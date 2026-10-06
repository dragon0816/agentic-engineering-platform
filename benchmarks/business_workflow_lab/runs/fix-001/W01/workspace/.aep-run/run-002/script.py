from pathlib import Path
import csv
p=Path('output/downloads/orders_export.csv')
print('exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
with p.open(newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
print('fieldnames', rows[0].keys() if rows else None)
print('rowcount', len(rows))
for r in rows[:20]: print(r)