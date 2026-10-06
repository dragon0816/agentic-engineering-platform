from pathlib import Path
import urllib.request
ws=Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES')
for p in sorted((ws/'input').iterdir()):
    print('-', p.name, p.stat().st_size)
notes=ws/'input'/'catalog_notes.md'
print('\nNOTES HEAD:')
print(notes.read_text(encoding='utf-8')[:2000])
url='http://127.0.0.1:49758/t10/catalog'
print('\nFETCH', url)
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data=r.read()
        print('status', r.status, 'content-type', r.headers.get('content-type'), 'bytes', len(data))
        text=data.decode('utf-8', errors='replace')
        print('PAGE HEAD:')
        print(text[:3000])
except Exception as e:
    print('FETCH ERROR', type(e).__name__, e)
