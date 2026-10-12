from pathlib import Path
import csv, json
ws=Path.cwd()
print('workspace', ws)
print('recursive input listing:')
for p in sorted((ws/'input').rglob('*')):
    print('-', p.relative_to(ws), 'dir' if p.is_dir() else f'file size={p.stat().st_size}')
    if p.is_file() and p.suffix.lower()=='.csv':
        print('  CSV sample')
        with p.open(newline='', encoding='utf-8-sig') as f:
            reader=csv.DictReader(f)
            print('  headers', reader.fieldnames)
            for i,row in zip(range(5), reader):
                print(' ', i+1, row)
    elif p.is_file() and p.name=='manifest.json':
        print('  manifest', p.read_text(encoding='utf-8'))