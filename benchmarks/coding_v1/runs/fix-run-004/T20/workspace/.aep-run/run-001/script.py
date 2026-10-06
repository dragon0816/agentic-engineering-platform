from pathlib import Path
import csv
base=Path('.')
print('Workspace:', base.resolve())
print('Top-level files:', [p.name for p in base.iterdir()])
print('Input files:')
for p in sorted((base/'input').glob('*')):
    print(' -', p.name, 'size=', p.stat().st_size)
print('\n--- supplied_sop.md preview ---')
sop=base/'input'/'supplied_sop.md'
if sop.exists():
    print(sop.read_text(encoding='utf-8', errors='replace')[:4000])
else:
    print('supplied_sop.md not found under input')
print('\n--- CSV previews ---')
for p in sorted((base/'input').glob('*.csv')):
    print(f'### {p.name}')
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        sample=f.read(2048)
        print(sample[:2048])