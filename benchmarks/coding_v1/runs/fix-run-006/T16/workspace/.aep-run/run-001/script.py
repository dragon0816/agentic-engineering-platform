from pathlib import Path
import json
base = Path('input')
print('Workspace:', Path.cwd())
print('Input exists:', base.exists())
for p in sorted(base.iterdir() if base.exists() else []):
    print('\nFILE', p.name, 'size', p.stat().st_size)
    try:
        txt = p.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        txt = p.read_text(encoding='utf-8-sig', errors='replace')
    lines = txt.splitlines()
    print('line_count', len(lines))
    for i, line in enumerate(lines[:5], 1):
        print(f'{i}: {line[:300]}')