from pathlib import Path
import csv
for p in sorted(Path('output/downloads').glob('*.csv')):
    print('\nFILE', p, 'bytes', p.stat().st_size)
    with open(p, newline='', encoding='utf-8-sig') as f:
        reader=csv.reader(f)
        for i,row in enumerate(reader):
            print(row)
            if i>=3: break