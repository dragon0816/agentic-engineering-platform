from pathlib import Path
import os
base=Path('.')
print('cwd', Path.cwd())
for p in sorted(Path('input').glob('*')):
    print(p, p.stat().st_size)
print('output exists', Path('output').exists())
