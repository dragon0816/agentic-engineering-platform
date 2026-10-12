from pathlib import Path
import csv
p=Path('output/downloads/orders_2026-09_open.csv')
print(p, p.exists(), p.stat().st_size if p.exists() else None)
with p.open(newline='', encoding='utf-8-sig') as f:
    reader=csv.DictReader(f)
    rows=list(reader)
print('headers', reader.fieldnames)
print('count', len(rows))
for r in rows:
    print(r)