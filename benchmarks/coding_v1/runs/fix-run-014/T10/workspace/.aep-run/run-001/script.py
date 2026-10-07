from pathlib import Path
from urllib.request import urlopen

ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print(' -', p.name, 'size=', p.stat().st_size)

notes = ws/'input'/'catalog_notes.md'
if notes.exists():
    print('\n--- input/catalog_notes.md ---')
    print(notes.read_text(encoding='utf-8'))

url = 'http://127.0.0.1:63668/t10/catalog'
print('\nFetching:', url)
with urlopen(url, timeout=10) as r:
    html = r.read().decode('utf-8', errors='replace')
print('HTML length:', len(html))
print('\n--- HTML first 3000 chars ---')
print(html[:3000])