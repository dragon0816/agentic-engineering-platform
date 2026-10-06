from pathlib import Path
from urllib.request import urlopen

ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').iterdir()):
    print('-', p.name, p.stat().st_size, 'bytes')

notes = ws/'input'/'catalog_notes.md'
print('\n--- catalog_notes.md ---')
print(notes.read_text(encoding='utf-8'))

url = 'http://127.0.0.1:57997/t10/catalog'
print('\n--- catalog page first 5000 chars ---')
with urlopen(url, timeout=10) as resp:
    data = resp.read()
    print('status', resp.status)
    print('content-type', resp.headers.get('content-type'))
    text = data.decode('utf-8', errors='replace')
    print(text[:5000])
    print('\nTOTAL_CHARS', len(text))