from pathlib import Path
from urllib.request import urlopen

ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print(' -', p.name, p.stat().st_size, 'bytes')

notes = ws/'input'/'catalog_notes.md'
if notes.exists():
    print('\n--- input/catalog_notes.md ---')
    print(notes.read_text(encoding='utf-8')[:4000])
else:
    print('catalog_notes.md not found')

url = 'http://127.0.0.1:54763/t10/catalog'
print('\nFetching:', url)
with urlopen(url, timeout=10) as r:
    data = r.read()
    final_url = r.geturl()
    ctype = r.headers.get('content-type')
print('final_url:', final_url)
print('content-type:', ctype)
text = data.decode('utf-8', errors='replace')
print('html length:', len(text))
print('\n--- page markup sample start ---')
print(text[:6000])
print('--- page markup sample end ---')