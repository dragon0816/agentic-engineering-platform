from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)
md = ws/'input'/'login_sop.md'
print('\nlogin_sop.md exists:', md.exists())
if md.exists():
    print('--- login_sop.md start ---')
    print(md.read_text(encoding='utf-8'))
    print('--- login_sop.md end ---')
