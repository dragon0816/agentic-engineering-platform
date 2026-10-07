from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
    if p.name.lower() == 'sop.md':
        txt = p.read_text(encoding='utf-8')
        print('--- sop.md preview start ---')
        print(txt[:4000])
        print('--- sop.md preview end ---')
