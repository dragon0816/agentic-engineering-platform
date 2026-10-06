from pathlib import Path
import json
base=Path('input')
print('Workspace:', Path.cwd())
print('Input exists:', base.exists())
for p in sorted(base.rglob('*')):
    if p.is_file():
        print('\nFILE', p, 'size', p.stat().st_size)
        try:
            with p.open('r', encoding='utf-8-sig') as f:
                for i,line in zip(range(5), f):
                    print(f'{i+1}: {line.rstrip()}')
        except UnicodeDecodeError:
            with p.open('r', encoding='utf-8', errors='replace') as f:
                for i,line in zip(range(5), f):
                    print(f'{i+1}: {line.rstrip()}')