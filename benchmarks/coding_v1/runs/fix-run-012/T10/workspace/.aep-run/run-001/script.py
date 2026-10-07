from pathlib import Path
import urllib.request

ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
for p in sorted((ws/'input').iterdir()):
    print('-', p.name, 'size=', p.stat().st_size)

notes = ws/'input'/'catalog_notes.md'
print('\n--- input/catalog_notes.md ---')
print(notes.read_text(encoding='utf-8'))

url = 'http://127.0.0.1:64212/t10/catalog'
print('\n--- URL:', url, '---')
with urllib.request.urlopen(url, timeout=10) as r:
    data = r.read()
    print('status', getattr(r, 'status', None), 'content-type', r.headers.get('content-type'), 'bytes', len(data))
    text = data.decode('utf-8', errors='replace')
print(text[:5000])