from pathlib import Path
import csv
ws=Path.cwd()
out=ws/'output'
print('output files:', [(p.name, p.stat().st_size) for p in sorted(out.iterdir())])
exp=out/'expense_E006_2026-01-01_2026-01-31.csv'
print('export exists:', exp.exists(), 'size:', exp.stat().st_size if exp.exists() else None)
if exp.exists():
    raw=exp.read_text(encoding='utf-8-sig')
    print('first 500 chars:', repr(raw[:500]))
    with exp.open(newline='', encoding='utf-8-sig') as f:
        reader=csv.reader(f)
        for i,row in zip(range(5), reader):
            print('csv row', i, row)