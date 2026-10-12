from pathlib import Path
import csv

ws = Path.cwd()
print('workspace=', ws)
input_dir = ws / 'input'
output_dir = ws / 'output'
print('input exists=', input_dir.exists())
print('output exists=', output_dir.exists())
print('input files:')
for p in sorted(input_dir.iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)

sop = input_dir / 'supplied_sop.md'
if sop.exists():
    print('\n--- supplied_sop.md preview ---')
    txt = sop.read_text(encoding='utf-8')
    print(txt[:4000])

print('\n--- CSV previews ---')
for p in sorted(input_dir.glob('*.csv')):
    print('\nCSV:', p.name)
    with p.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for i, row in zip(range(6), reader):
            print(i, row)
