from pathlib import Path
ws=Path.cwd()
print('workspace', ws)
for p in (ws/'input').glob('*'):
    print('INPUT_FILE', p.name, 'size', p.stat().st_size)
    if p.name.lower()=='specs.md':
        txt=p.read_text(encoding='utf-8')
        print('--- specs.md head ---')
        print(txt[:2000])
        print('--- end head ---')
