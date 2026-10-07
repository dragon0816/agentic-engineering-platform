from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
sop = ws/'input'/'sop.md'
print('\n--- sop.md preview ---')
text = sop.read_text(encoding='utf-8')
print(text[:4000])
print('--- end preview; total chars:', len(text), '---')