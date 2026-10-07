from pathlib import Path
import csv
ws=Path.cwd()
for name in ['approved_2026_09.csv']:
    print('\nALL CSV', name)
    with open(ws/'output'/name, newline='', encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            print(row)
