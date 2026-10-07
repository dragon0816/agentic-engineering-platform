from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
md = ws/'input'/'specs.md'
print('\nspecs.md exists:', md.exists())
if md.exists():
    text = md.read_text(encoding='utf-8')
    print('--- specs.md content start ---')
    print(text[:4000])
    print('--- specs.md content end ---')