from pathlib import Path
import os
base=Path('.')
print('CWD', Path.cwd())
for p in sorted(base.rglob('*')):
    rel=p.relative_to(base)
    if p.is_file():
        print('FILE', rel, p.stat().st_size)
    else:
        print('DIR ', rel)
