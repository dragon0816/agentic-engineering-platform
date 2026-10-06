from pathlib import Path
ws=Path.cwd()
print('workspace', ws)
for p in sorted((ws/'input').glob('*')):
    print('INPUT', p.name, 'size', p.stat().st_size)
    if p.name.lower()=='specs.md':
        text=p.read_text(encoding='utf-8')
        print('--- specs.md preview ---')
        print(text[:2000])
        print('--- end preview ---')
