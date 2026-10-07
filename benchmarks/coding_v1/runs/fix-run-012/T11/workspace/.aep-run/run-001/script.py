from pathlib import Path
from urllib.request import urlopen

workspace = Path.cwd()
print('workspace:', workspace)
print('input files:', [p.name for p in (workspace/'input').glob('*')])
print('output exists:', (workspace/'output').exists())
url = 'http://127.0.0.1:64212/t11/list'
with urlopen(url, timeout=10) as r:
    data = r.read().decode('utf-8', errors='replace')
    print('url:', url)
    print('status:', getattr(r, 'status', None))
    print('content-type:', r.headers.get('content-type'))
    print('markup first 2000 chars:')
    print(data[:2000])