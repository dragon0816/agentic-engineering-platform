from pathlib import Path
import csv
ws=Path.cwd(); out=ws/'output'
for fn in ['expenses_P001_2026-09.csv','expenses_P003_2026-09.csv']:
    p=out/fn
    print('\n',fn, p.exists(), p.stat().st_size if p.exists() else None)
    if p.exists():
        with open(p, newline='', encoding='utf-8-sig') as f:
            rdr=csv.reader(f)
            for i,row in zip(range(20),rdr):
                print(i,row)
