from pathlib import Path
from urllib.request import urlopen

ws=Path('.')
notes=ws/'input'/'catalog_notes.md'
print('NOTES EXISTS', notes.exists())
print(notes.read_text(encoding='utf-8')[:2000])
url='http://127.0.0.1:49257/t10/catalog'
try:
    with urlopen(url, timeout=10) as r:
        data=r.read()
        print('URL status', r.status, 'len', len(data), 'ctype', r.headers.get('content-type'))
        print(data[:3000].decode('utf-8', errors='replace'))
except Exception as e:
    print('FETCH ERROR', type(e).__name__, e)
