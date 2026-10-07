from pathlib import Path
import csv
ws=Path.cwd()
for name in ['expenses_P001_2026-09.csv','expenses_P003_2026-09.csv']:
    p=ws/'output'/name
    print('\n--', name, p.exists(), p.stat().st_size if p.exists() else None)
    if p.exists():
        with open(p, newline='', encoding='utf-8-sig') as f:
            r=csv.reader(f)
            for i,row in zip(range(12), r): print(i,row)