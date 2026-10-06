from pathlib import Path
import os, sys, json
from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError

workspace = Path.cwd()
print('WORKSPACE', workspace)
print('INPUT FILES:')
for p in sorted((workspace/'input').glob('**/*')):
    print('-', p.relative_to(workspace), 'file' if p.is_file() else 'dir')

url='http://127.0.0.1:56996/t13/list'
print('\nFETCH LIST:', url)
try:
    req=Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urlopen(req, timeout=10) as r:
        data=r.read(5000)
        print('status', r.status, 'content-type', r.headers.get('content-type'))
        text=data.decode('utf-8', errors='replace')
        print('sample markup start')
        print(text[:2000])
        print('sample markup end')
except Exception as e:
    print('ERROR fetching list', type(e).__name__, e)
