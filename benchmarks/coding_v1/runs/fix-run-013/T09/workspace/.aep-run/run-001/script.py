from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
login = ws/'input'/'login_sop.md'
print('\nlogin_sop.md exists:', login.exists())
if login.exists():
    text = login.read_text(encoding='utf-8')
    print('--- login_sop.md ---')
    print(text[:4000])
    print('--- end ---')