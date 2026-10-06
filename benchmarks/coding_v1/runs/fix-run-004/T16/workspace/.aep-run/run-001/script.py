from pathlib import Path
import json
base = Path('input')
print('Workspace:', Path.cwd())
print('Input exists:', base.exists())
for p in sorted(base.rglob('*')):
    if p.is_file():
        print('\nFILE', p.as_posix(), 'size', p.stat().st_size)
        try:
            text = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            text = p.read_text(encoding='utf-8-sig', errors='replace')
        lines = text.splitlines()
        print('line_count', len(lines))
        for i, line in enumerate(lines[:5], 1):
            print(f'{i}: {line[:300]}')
print('\nOutput exists:', Path('output').exists())