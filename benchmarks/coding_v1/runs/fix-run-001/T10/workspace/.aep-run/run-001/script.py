from pathlib import Path
from urllib.request import urlopen, Request

base=Path('.')
print('Workspace', base.resolve())
notes=Path('input/catalog_notes.md')
print('Notes exists', notes.exists())
if notes.exists():
    print('--- NOTES ---')
    print(notes.read_text(encoding='utf-8'))

url='http://127.0.0.1:64664/t10/catalog'
req=Request(url, headers={'User-Agent':'Mozilla/5.0'})
with urlopen(req, timeout=10) as r:
    data=r.read()
    print('Status', r.status, 'Content-Type', r.headers.get('content-type'), 'len', len(data))
    text=data.decode(r.headers.get_content_charset() or 'utf-8', errors='replace')
    print('--- HTML HEAD ---')
    print(text[:5000])
    Path('output/debug_catalog.html').write_text(text, encoding='utf-8')
    print('Wrote output/debug_catalog.html')