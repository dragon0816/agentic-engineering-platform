from pathlib import Path
import csv, json
base=Path('.')
print('Recursive input listing:')
for p in sorted((base/'input').rglob('*')):
    print(('DIR ' if p.is_dir() else 'FILE'), p.relative_to(base), 'size=', (p.stat().st_size if p.is_file() else ''))
    if p.is_file() and p.suffix.lower()=='.csv':
        print('  CSV sample:')
        with p.open(newline='', encoding='utf-8-sig', errors='replace') as f:
            r=csv.reader(f)
            for i,row in zip(range(8), r): print('   ', row)
    elif p.is_file() and p.name=='manifest.json':
        print('  manifest:', p.read_text(encoding='utf-8', errors='replace'))
