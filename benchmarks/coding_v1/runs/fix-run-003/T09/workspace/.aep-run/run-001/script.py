from pathlib import Path
import os, json
root=Path('.')
print('cwd', Path.cwd())
print('input files:', [str(p) for p in Path('input').rglob('*')])
for p in Path('input').rglob('*'):
    if p.is_file():
        print('\n---', p, '---')
        print(p.read_text(encoding='utf-8', errors='replace')[:4000])
print('\nroot files:', [str(p) for p in root.iterdir()])
print('output exists', Path('output').exists())