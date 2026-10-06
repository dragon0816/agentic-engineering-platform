from pathlib import Path
workspace = Path.cwd()
print('WORKSPACE', workspace)
print('INPUT FILES:')
for p in sorted((workspace/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)
sop = workspace/'input'/'sop.md'
print('\nSOP EXISTS:', sop.exists())
if sop.exists():
    text = sop.read_text(encoding='utf-8')
    print('--- sop.md first 2000 chars ---')
    print(text[:2000])
    print('--- end sample ---')