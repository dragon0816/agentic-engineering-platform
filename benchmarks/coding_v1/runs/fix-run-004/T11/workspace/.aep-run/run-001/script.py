import os, urllib.request
from pathlib import Path
print('CWD', os.getcwd())
print('input files:', [p.name for p in Path('input').glob('*')])
print('output exists:', Path('output').exists())
url='http://127.0.0.1:58649/t11/list'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data=r.read(3000)
        print('status', r.status, 'content-type', r.headers.get('content-type'))
        print(data.decode('utf-8', errors='replace')[:3000])
except Exception as e:
    print('ERROR', type(e).__name__, e)