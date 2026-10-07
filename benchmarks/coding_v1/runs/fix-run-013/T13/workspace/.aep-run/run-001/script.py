import os, urllib.request, urllib.error
from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
print('input files:', [p.name for p in (ws/'input').glob('*')])
print('output exists:', (ws/'output').exists())
url = 'http://127.0.0.1:63795/t13/list'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        print('list status:', r.status)
        data = r.read(4000)
        print('list content-type:', r.headers.get('content-type'))
        print('list sample:')
        print(data.decode('utf-8', errors='replace'))
except Exception as e:
    print('list fetch error:', repr(e))