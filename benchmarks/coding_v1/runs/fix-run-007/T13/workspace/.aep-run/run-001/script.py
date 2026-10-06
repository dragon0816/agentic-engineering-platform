import os, urllib.request, urllib.error
from pathlib import Path
ws = Path.cwd()
print('workspace:', ws)
print('input exists:', (ws/'input').exists())
print('output exists:', (ws/'output').exists())
print('input files:', [p.name for p in (ws/'input').glob('*')] if (ws/'input').exists() else [])
url = 'http://127.0.0.1:57997/t13/list'
print('fetching list:', url)
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = resp.read()
        print('status:', resp.status)
        print('content-type:', resp.headers.get('content-type'))
        text = data.decode('utf-8', errors='replace')
        print('page sample start:')
        print(text[:2000])
        print('page sample end')
except urllib.error.HTTPError as e:
    print('HTTPError:', e.code, e.reason)
    print(e.read().decode('utf-8', errors='replace')[:1000])
except Exception as e:
    print('ERROR:', repr(e))