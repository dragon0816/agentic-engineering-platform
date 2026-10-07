from pathlib import Path
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
sop = ws/'input'/'supplied_sop.md'
print('\nSUPPLIED_SOP_EXISTS', sop.exists())
if sop.exists():
    print('\n--- supplied_sop.md ---')
    print(sop.read_text(encoding='utf-8'))
print('\nOUTPUT FILES BEFORE:')
out = ws/'output'
out.mkdir(exist_ok=True)
for p in sorted(out.glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)