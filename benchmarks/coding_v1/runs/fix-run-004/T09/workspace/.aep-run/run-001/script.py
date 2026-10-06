from pathlib import Path
import os
ws=Path.cwd()
print('cwd=', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
    if p.name.lower().endswith(('.md','.txt','.json','.csv')):
        print('---', p.name, 'head ---')
        print(p.read_text(encoding='utf-8')[:2000])
        print('--- end head ---')
print('output exists=', (ws/'output').exists())