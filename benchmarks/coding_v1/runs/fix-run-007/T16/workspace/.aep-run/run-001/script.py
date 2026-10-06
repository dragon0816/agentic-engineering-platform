from pathlib import Path
import json
ws = Path.cwd()
print('workspace:', ws)
for sub in ['input','output']:
    p = ws/sub
    print(sub, 'exists=', p.exists(), 'files=', [x.name for x in p.iterdir()] if p.exists() else None)
print('\nInput file inspection:')
for path in sorted((ws/'input').iterdir()):
    if path.is_file():
        print(f'--- {path.name} size={path.stat().st_size}')
        try:
            lines = path.read_text(encoding='utf-8').splitlines()
        except UnicodeDecodeError:
            lines = path.read_text(encoding='utf-8-sig').splitlines()
        print('line_count:', len(lines))
        for i, line in enumerate(lines[:5], 1):
            print(f'{i}: {line[:300]}')
