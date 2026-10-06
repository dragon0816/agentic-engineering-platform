from pathlib import Path
root=Path('.')
print('Workspace:', root.resolve())
print('Input files:')
for p in sorted((root/'input').iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)
    if p.name.lower()=='sop.md':
        text=p.read_text(encoding='utf-8')
        print('--- sop.md first 120 lines ---')
        for i,line in enumerate(text.splitlines()[:120],1):
            print(f'{i:03d}: {line}')
        print('--- end preview ---')