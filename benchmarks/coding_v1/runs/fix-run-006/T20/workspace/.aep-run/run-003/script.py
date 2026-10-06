from pathlib import Path
import csv, json
ws=Path.cwd()
print('workspace', ws)
print('input files:')
for p in sorted((ws/'input').rglob('*')):
    if p.is_file():
        print('-', p.relative_to(ws), p.stat().st_size)
print('\nSOP preview:')
sop=ws/'input'/'supplied_sop.md'
print(sop.read_text(encoding='utf-8')[:2000])
print('\nCSV files and sample:')
for p in sorted((ws/'input').rglob('*.csv')):
    print('CSV', p.relative_to(ws))
    with p.open(newline='', encoding='utf-8-sig') as f:
        r=csv.reader(f)
        for i,row in zip(range(6), r):
            print(i, row)
print('\nmanifest:')
mp=ws/'input'/'manifest.json'
if mp.exists(): print(mp.read_text(encoding='utf-8')[:1000])