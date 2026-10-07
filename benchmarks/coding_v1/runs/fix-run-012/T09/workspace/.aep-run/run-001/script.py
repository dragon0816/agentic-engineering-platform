from pathlib import Path
import os
ws=Path.cwd()
print('workspace=', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
    if p.name == 'login_sop.md':
        print('--- login_sop.md ---')
        print(p.read_text(encoding='utf-8'))
        print('--- end ---')
print('output files:')
out=ws/'output'
out.mkdir(exist_ok=True)
for p in sorted(out.glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)