from pathlib import Path
ws = Path.cwd()
print('workspace=', ws)
for p in sorted((ws/'input').iterdir()):
    print('input file:', p.name, 'size=', p.stat().st_size)
    if p.name.lower() == 'specs.md':
        txt = p.read_text(encoding='utf-8')
        print('--- specs.md content start ---')
        print(txt)
        print('--- specs.md content end ---')