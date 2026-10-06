import os, json, urllib.request
from pathlib import Path
print('CWD', os.getcwd())
print('input files:', [p.name for p in Path('input').glob('*')])
print('output exists:', Path('output').exists())
url='http://127.0.0.1:58649/t13/list'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data=r.read(2000)
        print('list status:', r.status)
        print('list content-type:', r.headers.get('content-type'))
        print('list sample:', data.decode('utf-8','replace')[:2000])
except Exception as e:
    print('fetch error:', type(e).__name__, str(e))