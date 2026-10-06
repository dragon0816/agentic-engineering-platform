from pathlib import Path
ws=Path.cwd()
print('cwd', ws)
for p in sorted((ws/'input').glob('*')):
    print('FILE', p.name, p.stat().st_size)
    if p.suffix.lower() in ['.md','.txt','.csv']:
        print('---',p.name,'---')
        print(p.read_text(encoding='utf-8-sig'))
        print('--- end ---')
