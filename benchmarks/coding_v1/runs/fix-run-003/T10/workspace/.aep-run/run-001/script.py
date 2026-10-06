from pathlib import Path
from urllib.request import urlopen, Request

ws=Path('.')
print('workspace', ws.resolve())
notes=Path('input/catalog_notes.md').read_text(encoding='utf-8')
print('--- NOTES ---')
print(notes[:4000])
url='http://127.0.0.1:51979/t10/catalog'
req=Request(url, headers={'User-Agent':'Mozilla/5.0'})
with urlopen(req, timeout=10) as r:
    html=r.read().decode('utf-8', errors='replace')
print('--- HTML length', len(html), '---')
print(html[:5000])
