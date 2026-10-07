from pathlib import Path
import csv
base = Path('.')
print('Workspace:', base.resolve())
print('Input files:')
for p in sorted((base/'input').glob('*')):
    print(' -', p.name, 'size=', p.stat().st_size)
print('Output files currently:')
out = base/'output'
out.mkdir(exist_ok=True)
for p in sorted(out.glob('*')):
    print(' -', p.name, 'size=', p.stat().st_size)

sop = base/'input'/'supplied_sop.md'
if sop.exists():
    print('\n--- supplied_sop.md ---')
    print(sop.read_text(encoding='utf-8'))
else:
    print('supplied_sop.md not found under input')

print('\n--- CSV previews ---')
for p in sorted((base/'input').glob('*.csv')):
    print(f'CSV: {p.name}')
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        for i, row in zip(range(6), reader):
            print(' row', i+1, row)
    print()