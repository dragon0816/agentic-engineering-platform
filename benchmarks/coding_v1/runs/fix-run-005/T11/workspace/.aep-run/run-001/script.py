import os, urllib.request
from pathlib import Path
workspace=Path.cwd()
print('CWD', workspace)
print('input files:', [p.name for p in (workspace/'input').glob('*')])
url='http://127.0.0.1:49758/t11/list'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data=r.read().decode('utf-8', errors='replace')
    print('list url status OK')
    print('list page first 2000 chars:\n', data[:2000])
except Exception as e:
    print('ERROR fetching list:', repr(e))