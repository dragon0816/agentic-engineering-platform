from pathlib import Path
from urllib.request import urlopen

ws = Path.cwd()
print('workspace:', ws)
print('input files:', [p.name for p in (ws/'input').glob('*')] if (ws/'input').exists() else 'no input dir')
url = 'http://127.0.0.1:64493/t11/list'
with urlopen(url, timeout=10) as r:
    data = r.read().decode('utf-8', errors='replace')
print('list url:', url)
print('status: fetched')
print('markup sample:')
print(data[:3000])