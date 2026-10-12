from pathlib import Path
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
md = ws/'input'/'sop.md'
if md.exists():
    text = md.read_text(encoding='utf-8')
    print('\n--- sop.md first 2000 chars ---')
    print(text[:2000])
    print('--- total chars:', len(text), '---')
else:
    print('sop.md not found')