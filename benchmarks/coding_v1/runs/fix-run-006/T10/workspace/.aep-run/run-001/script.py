from pathlib import Path
import urllib.request

ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').iterdir()):
    print('-', p.name, p.stat().st_size, 'bytes')
    if p.name == 'catalog_notes.md':
        print('--- catalog_notes.md ---')
        print(p.read_text(encoding='utf-8')[:2000])

url = 'http://127.0.0.1:56996/t10/catalog'
print('\nFetching:', url)
with urllib.request.urlopen(url, timeout=10) as r:
    data = r.read()
    print('status:', r.status)
    print('content-type:', r.headers.get('content-type'))
    text = data.decode('utf-8', errors='replace')
    print('length:', len(text))
    print('--- page sample ---')
    print(text[:4000])