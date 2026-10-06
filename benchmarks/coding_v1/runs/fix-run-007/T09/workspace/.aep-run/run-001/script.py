from pathlib import Path
base=Path.cwd()
print('workspace=', base)
print('input files:')
for p in sorted((base/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
sop=base/'input'/'login_sop.md'
print('\nlogin_sop.md exists:', sop.exists())
if sop.exists():
    print('--- login_sop.md ---')
    print(sop.read_text(encoding='utf-8'))