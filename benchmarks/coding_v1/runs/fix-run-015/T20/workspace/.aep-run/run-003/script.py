from pathlib import Path
import csv

ws = Path.cwd()
input_dir = ws / 'input'
print('recursive input listing:')
for p in sorted(input_dir.rglob('*')):
    kind = 'dir' if p.is_dir() else 'file'
    print(f' - {p.relative_to(ws)} [{kind}] size={p.stat().st_size}')

print('\nCSV/file previews:')
for p in sorted(input_dir.rglob('*')):
    if p.is_file() and (p.suffix.lower() == '.csv' or p.name.lower() == 'results.csv'):
        print('\nFILE:', p.relative_to(ws))
        with p.open(newline='', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            for i, row in zip(range(8), reader):
                print(i, row)
