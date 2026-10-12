import csv
from pathlib import Path
with open('output/downloads/all_orders_export.csv', newline='', encoding='utf-8-sig') as f:
    ids=[r['OrderID'] for r in csv.DictReader(f)]
print(len(ids))
print(ids)
