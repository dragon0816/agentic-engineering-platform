from pathlib import Path
import json, os
ws=Path.cwd()
print('TREE input:')
for p in sorted((ws/'input').rglob('*')):
    typ='dir' if p.is_dir() else 'file'
    print('-', p.relative_to(ws), typ, 'size=', p.stat().st_size)
print('\nmanifest:')
mp=ws/'input'/'manifest.json'
print(mp.read_text(encoding='utf-8') if mp.exists() else 'missing')
