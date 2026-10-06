from pathlib import Path
ws=Path.cwd()
for p in sorted((ws/'input').rglob('*')):
    if p.is_file():
        print('FILE', p.relative_to(ws/'input'), p.stat().st_size)
        if p.suffix.lower() in ['.json','.csv','.md','.txt']:
            print(p.read_text(encoding='utf-8-sig'))
            print('---')
