from pathlib import Path
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)

sop = ws/'input'/'sop.md'
print('\n--- sop.md preview ---')
text = sop.read_text(encoding='utf-8')
for i, line in enumerate(text.splitlines()[:80], 1):
    print(f'{i:03}: {line}')
print('--- total lines:', len(text.splitlines()), '---')