from pathlib import Path
import csv
ws=Path.cwd()
for fn in ['expenses_P001_Approved_2026-09.csv','expenses_P003_Approved_2026-09.csv']:
    p=ws/'output'/fn
    print('---',fn,p.exists(), p.stat().st_size if p.exists() else '')
    if p.exists():
        for enc in ['utf-8-sig','cp950','utf-8']:
            try:
                with open(p, newline='', encoding=enc) as f:
                    rows=list(csv.DictReader(f))
                print('enc',enc,'headers',rows[0].keys() if rows else [])
                for r in rows: print(r)
                break
            except Exception as e: print('enc fail',enc,e)
