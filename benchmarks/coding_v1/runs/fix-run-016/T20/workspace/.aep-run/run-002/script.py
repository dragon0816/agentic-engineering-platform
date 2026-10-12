from pathlib import Path
import csv, json
ws=Path.cwd()
print('workspace', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size', p.stat().st_size)
    if p.suffix.lower()=='.md':
        text=p.read_text(encoding='utf-8')
        print('---', p.name, 'first 2000 chars ---')
        print(text[:2000])
    elif p.suffix.lower()=='.csv':
        print('---', p.name, 'sample ---')
        with p.open(newline='', encoding='utf-8-sig') as f:
            reader=csv.DictReader(f)
            print('headers', reader.fieldnames)
            for i,row in zip(range(5), reader):
                print(i+1, row)
print('output files currently:')
out=ws/'output'
out.mkdir(exist_ok=True)
for p in sorted(out.glob('*')):
    print('-', p.name, p.stat().st_size)