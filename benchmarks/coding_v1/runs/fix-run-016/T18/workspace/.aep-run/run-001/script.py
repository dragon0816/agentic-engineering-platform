from pathlib import Path
import csv

ws = Path.cwd()
print('WORKSPACE', ws)
for p in sorted((ws/'input').iterdir()):
    print('INPUT_FILE', p.name, 'size=', p.stat().st_size)

for name in ['DEPENDENCIES.txt', 'export.py', 'input.csv']:
    p = ws/'input'/name
    print('\n---', name, 'exists=', p.exists(), '---')
    if not p.exists():
        continue
    if name.endswith('.csv'):
        with p.open('r', newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            rows = []
            for i, row in enumerate(reader):
                rows.append(row)
                if i >= 5:
                    break
        print('CSV_SAMPLE_ROWS')
        for row in rows:
            print(row)
    else:
        text = p.read_text(encoding='utf-8', errors='replace')
        print(text[:4000])
