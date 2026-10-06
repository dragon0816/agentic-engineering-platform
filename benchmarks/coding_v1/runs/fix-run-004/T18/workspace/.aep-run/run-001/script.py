from pathlib import Path
import csv
ws=Path('.')
print('cwd', ws.resolve())
print('input files:', [p.name for p in (ws/'input').iterdir()])
for name in ['export.py','input.csv','DEPENDENCIES.txt']:
    p=ws/'input'/name
    print('\n---', p, 'exists', p.exists(), 'size', p.stat().st_size if p.exists() else None)
    if p.exists():
        if name.endswith('.csv'):
            with p.open(newline='', encoding='utf-8-sig') as f:
                rows=list(csv.reader(f))
            print('csv rows count', len(rows))
            for r in rows[:6]: print(r)
        else:
            print(p.read_text(encoding='utf-8', errors='replace')[:2000])