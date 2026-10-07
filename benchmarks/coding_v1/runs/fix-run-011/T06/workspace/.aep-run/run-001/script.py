from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
sop = ws/'input'/'sop.md'
print('\n--- sop.md preview ---')
text = sop.read_text(encoding='utf-8')
for i, line in enumerate(text.splitlines()[:120], 1):
    print(f'{i:03}: {line}')