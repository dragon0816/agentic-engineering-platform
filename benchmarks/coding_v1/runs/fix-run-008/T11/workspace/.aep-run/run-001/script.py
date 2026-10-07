from pathlib import Path
from urllib.request import urlopen

workspace = Path.cwd()
print('workspace:', workspace)
print('input files:', [p.name for p in (workspace/'input').iterdir()] if (workspace/'input').exists() else 'NO input dir')
url = 'http://127.0.0.1:64650/t11/list'
with urlopen(url, timeout=10) as r:
    html = r.read().decode('utf-8', errors='replace')
print('list url:', url)
print('list html length:', len(html))
print('list html sample:')
print(html[:2000])