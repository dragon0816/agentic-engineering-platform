import os, csv
from pathlib import Path
ws=Path.cwd()
print('workspace', ws)
for root, dirs, files in os.walk(ws/'input'):
    rel=Path(root).relative_to(ws)
    print('DIR', rel)
    for f in sorted(files):
        p=Path(root)/f
        print('  FILE', f, 'size', p.stat().st_size)
        if f.lower().endswith('.csv'):
            with p.open('r', encoding='utf-8-sig', newline='') as fh:
                reader=csv.DictReader(fh)
                print('    headers', reader.fieldnames)
                for i,row in zip(range(5), reader):
                    print('    row', i+1, row)
