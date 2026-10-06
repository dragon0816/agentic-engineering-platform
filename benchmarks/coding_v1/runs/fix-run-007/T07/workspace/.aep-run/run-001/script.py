from pathlib import Path
ws = Path.cwd()
print('Workspace:', ws)
print('Input files:')
for p in sorted((ws/'input').iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)
md = ws/'input'/'specs.md'
print('\nspecs.md exists:', md.exists())
if md.exists():
    text = md.read_text(encoding='utf-8')
    print('\n--- specs.md content preview ---')
    print(text[:4000])
    print('--- end preview ---')
print('Output dir exists:', (ws/'output').exists())