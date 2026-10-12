from pathlib import Path
import csv
ws=Path.cwd()
for name in ['expense_P003_2026-09_approved.csv','expense_all_approved_2026-09.csv']:
    p=ws/'output'/name
    print('\n', name, p.exists(), p.stat().st_size if p.exists() else None)
    if p.exists():
        with open(p, newline='', encoding='utf-8-sig') as f:
            rdr=csv.reader(f)
            for i,row in zip(range(20), rdr): print(row)
