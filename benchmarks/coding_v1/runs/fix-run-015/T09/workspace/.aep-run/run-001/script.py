from pathlib import Path
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
md = ws/'input'/'login_sop.md'
print('\nlogin_sop.md exists:', md.exists())
if md.exists():
    print('\n--- login_sop.md ---')
    print(md.read_text(encoding='utf-8'))
    print('--- end ---')
