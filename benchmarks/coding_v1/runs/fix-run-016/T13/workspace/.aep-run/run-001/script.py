from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
input_dir = ws / 'input'
if input_dir.exists():
    for p in sorted(input_dir.rglob('*')):
        print(' -', p.relative_to(ws), 'dir' if p.is_dir() else f'{p.stat().st_size} bytes')
else:
    print(' input dir missing')

url = 'http://127.0.0.1:64493/t13/list'
print('\nFETCH LIST:', url)
try:
    req = Request(url, headers={'User-Agent':'AEP-inspect/1.0'})
    with urlopen(req, timeout=10) as resp:
        data = resp.read()
        print('STATUS', resp.status)
        print('CONTENT-TYPE', resp.headers.get('Content-Type'))
        text = data.decode('utf-8', errors='replace')
        print('PAGE MARKUP SAMPLE:')
        print(text[:4000])
except HTTPError as e:
    print('HTTPError', e.code, e.reason)
    body = e.read().decode('utf-8', errors='replace')
    print(body[:2000])
except URLError as e:
    print('URLError', e)
