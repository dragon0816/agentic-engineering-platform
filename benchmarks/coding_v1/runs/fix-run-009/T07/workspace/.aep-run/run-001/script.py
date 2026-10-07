from pathlib import Path
ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
md = ws/'input'/'specs.md'
print('\n--- specs.md preview ---')
text = md.read_text(encoding='utf-8')
print(text[:4000])
print('--- end preview ---')
print('Paragraph-like blocks:', len([b for b in text.split('\n\n') if b.strip()]))