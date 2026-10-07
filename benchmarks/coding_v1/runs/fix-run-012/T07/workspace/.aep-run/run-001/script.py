from pathlib import Path
workspace = Path.cwd()
print('WORKSPACE', workspace)
print('INPUT FILES:')
for p in sorted((workspace/'input').iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
md = workspace/'input'/'specs.md'
print('\nSPECS EXISTS:', md.exists())
if md.exists():
    text = md.read_text(encoding='utf-8')
    print('--- specs.md first 3000 chars ---')
    print(text[:3000])
    print('--- total chars ---', len(text))