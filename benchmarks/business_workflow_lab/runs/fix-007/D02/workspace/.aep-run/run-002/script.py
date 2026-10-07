from pathlib import Path
import csv
ws=Path.cwd()
print('OUTPUT FILES')
for p in sorted((ws/'output').glob('*')):
    print(p.name, p.stat().st_size)
    if p.suffix.lower()=='.csv':
        with open(p, newline='', encoding='utf-8-sig') as f:
            r=csv.reader(f)
            for i,row in zip(range(5), r): print(' ', row)
