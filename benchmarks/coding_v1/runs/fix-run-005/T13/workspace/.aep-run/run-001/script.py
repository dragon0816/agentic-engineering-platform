from pathlib import Path
import urllib.request, urllib.error

ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in (ws/'input').glob('*'):
    print(' -', p.name, 'size=', p.stat().st_size)
url='http://127.0.0.1:49758/t13/list'
print('fetch list:', url)
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data=r.read(2000)
        print('status:', r.status, 'content-type:', r.headers.get('content-type'))
        print('markup sample:')
        print(data.decode('utf-8', errors='replace'))
except Exception as e:
    print('ERROR fetching list:', repr(e))