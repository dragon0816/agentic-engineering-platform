from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)

sop = ws/'input'/'login_sop.md'
if sop.exists():
    print('\n--- login_sop.md ---')
    print(sop.read_text(encoding='utf-8'))
else:
    print('login_sop.md not found')

print('\noutput files currently:')
out = ws/'output'
out.mkdir(exist_ok=True)
for p in sorted(out.glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)