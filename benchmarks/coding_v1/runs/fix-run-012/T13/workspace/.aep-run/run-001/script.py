import os, urllib.request
from pathlib import Path
workspace = Path.cwd()
print('workspace:', workspace)
print('input files:', [p.name for p in (workspace/'input').glob('*')] if (workspace/'input').exists() else 'no input dir')
print('output exists:', (workspace/'output').exists())
url='http://127.0.0.1:64212/t13/list'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data=r.read(2000)
        print('list status:', r.status)
        print('content-type:', r.headers.get('content-type'))
        print('sample markup:\n', data.decode('utf-8','replace')[:2000])
except Exception as e:
    print('list fetch error:', type(e).__name__, e)