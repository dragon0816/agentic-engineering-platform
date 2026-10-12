from pathlib import Path
from urllib.request import urlopen

ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, p.stat().st_size, 'bytes')
notes = ws/'input'/'catalog_notes.md'
if notes.exists():
    print('\nCATALOG NOTES:')
    print(notes.read_text(encoding='utf-8')[:2000])
url = 'http://127.0.0.1:50447/t10/catalog'
print('\nFETCH', url)
with urlopen(url, timeout=10) as r:
    print('STATUS', getattr(r, 'status', None), 'CONTENT-TYPE', r.headers.get('content-type'))
    html = r.read().decode('utf-8', errors='replace')
print('HTML LENGTH', len(html))
print('HTML SAMPLE START')
print(html[:4000])
print('HTML SAMPLE END')