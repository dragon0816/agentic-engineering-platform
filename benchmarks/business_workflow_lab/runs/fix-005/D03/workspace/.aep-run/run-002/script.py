from pathlib import Path
import csv
ws=Path.cwd()
print('output files now:', [p.name for p in (ws/'output').iterdir()])
p=ws/'output'/'expense_export.csv'
print('expense_export exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
if p.exists():
    with p.open(newline='', encoding='utf-8-sig') as f:
        r=csv.reader(f)
        for i,row in zip(range(8), r):
            print(' row', i, row)
