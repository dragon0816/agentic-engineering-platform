from pathlib import Path
import os, json
base=Path.cwd()
print('CWD', base)
print('Workspace entries:')
for p in sorted(base.rglob('*')):
    rel=p.relative_to(base)
    if 'output' in rel.parts:
        continue
    print(('DIR ' if p.is_dir() else 'FILE'), rel)
print('\nlogin_sop candidates:')
for p in base.rglob('login_sop.md'):
    print('---', p.relative_to(base), '---')
    print(p.read_text(encoding='utf-8', errors='replace'))
