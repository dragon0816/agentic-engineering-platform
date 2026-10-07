from pathlib import Path
import csv
base=Path('.')
print('Workspace:', base.resolve())
print('Input files:')
for p in sorted((base/'input').iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)
print('\nexport.py preview:')
print((base/'input'/'export.py').read_text(encoding='utf-8'))
print('\nDEPENDENCIES.txt:')
print((base/'input'/'DEPENDENCIES.txt').read_text(encoding='utf-8'))
print('\ninput.csv headers and sample rows:')
with open(base/'input'/'input.csv', newline='', encoding='utf-8-sig') as f:
    r=csv.reader(f)
    for i,row in zip(range(8), r):
        print(i, row)
