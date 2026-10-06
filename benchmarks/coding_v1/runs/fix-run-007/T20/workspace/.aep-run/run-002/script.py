from pathlib import Path
import json, csv
ws=Path.cwd()
print('Recursive input tree:')
for p in sorted((ws/'input').rglob('*')):
    kind='DIR' if p.is_dir() else 'FILE'
    print(kind, p.relative_to(ws), 'size=' + (str(p.stat().st_size) if p.is_file() else ''))
manifest=ws/'input'/'manifest.json'
print('\nmanifest.json:')
print(manifest.read_text(encoding='utf-8', errors='replace') if manifest.exists() else 'MISSING')
print('\nCSV samples recursive:')
for p in sorted((ws/'input').rglob('*.csv')):
    print('\nFILE', p.relative_to(ws/'input'))
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        reader=csv.reader(f)
        for i,row in zip(range(8), reader):
            print(i, row)
