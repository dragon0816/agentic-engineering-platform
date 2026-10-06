from pathlib import Path
import csv
ws=Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES')
for p in sorted((ws/'input').iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
print('\nDEPENDENCIES.txt:')
print((ws/'input'/'DEPENDENCIES.txt').read_text(encoding='utf-8', errors='replace'))
print('\ninput.csv sample:')
with open(ws/'input'/'input.csv', newline='', encoding='utf-8-sig') as f:
    r=csv.reader(f)
    for i,row in zip(range(10), r):
        print(i, row)
print('\nexport.py:')
print((ws/'input'/'export.py').read_text(encoding='utf-8', errors='replace'))