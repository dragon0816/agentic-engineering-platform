from pathlib import Path
import csv, json
ws = Path.cwd()
print('WORKSPACE', ws)
print('Recursive input listing:')
for p in sorted((ws/'input').rglob('*')):
    print('-', p.relative_to(ws/'input'), 'dir=' + str(p.is_dir()), 'size=' + (str(p.stat().st_size) if p.is_file() else '-'))

manifest = ws/'input'/'manifest.json'
if manifest.exists():
    print('\n=== manifest.json ===')
    print(manifest.read_text(encoding='utf-8', errors='replace'))

print('\n=== CSV previews recursive ===')
for p in sorted((ws/'input').rglob('*.csv')):
    print('\nCSV:', p.relative_to(ws/'input'))
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        sample = f.read(4096)
        f.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample)
        except Exception:
            dialect = csv.excel
        reader = csv.reader(f, dialect)
        for i, row in zip(range(8), reader):
            print(i, row)
