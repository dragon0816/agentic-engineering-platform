from pathlib import Path
ws = Path.cwd()
print('workspace=', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
login = ws/'input'/'login_sop.md'
if login.exists():
    print('\n--- login_sop.md ---')
    print(login.read_text(encoding='utf-8'))
else:
    print('login_sop.md not found')
print('\noutput dir exists=', (ws/'output').exists())