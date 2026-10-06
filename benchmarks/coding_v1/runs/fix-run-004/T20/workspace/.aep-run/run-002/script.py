from pathlib import Path
base=Path('.')
print('Recursive input listing:')
for p in sorted((base/'input').rglob('*')):
    print(('DIR ' if p.is_dir() else 'FILE'), p.relative_to(base), 'size=', p.stat().st_size)
    if p.is_file() and p.suffix.lower() in {'.csv','.json','.md','.txt'}:
        print('--- preview', p.name, '---')
        print(p.read_text(encoding='utf-8-sig', errors='replace')[:1000])