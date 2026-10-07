from pathlib import Path
import urllib.request

ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)
notes = ws/'input'/'catalog_notes.md'
if notes.exists():
    print('\n--- catalog_notes.md ---')
    print(notes.read_text(encoding='utf-8'))
url='http://127.0.0.1:50351/t10/catalog'
print('\n--- fetching catalog ---')
with urllib.request.urlopen(url, timeout=10) as resp:
    print('status:', getattr(resp, 'status', None), 'content-type:', resp.headers.get('content-type'), 'url:', resp.geturl())
    data = resp.read(3000)
text=data.decode('utf-8', errors='replace')
print('first 3000 chars:')
print(text)
