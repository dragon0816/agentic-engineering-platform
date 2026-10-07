import os, urllib.request
from pathlib import Path
workspace=Path.cwd()
print('workspace', workspace)
print('input files:', [p.name for p in (workspace/'input').glob('*')])
urls=['http://127.0.0.1:50351/t12/a','http://127.0.0.1:50351/t12/b','http://127.0.0.1:50351/t12/c']
for url in urls:
    print('\nURL:', url)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data=r.read()
            print('status:', getattr(r,'status',None), 'content-type:', r.headers.get('content-type'), 'bytes:', len(data))
            text=data.decode('utf-8', errors='replace')
            print('sample:', text[:1000].replace('\n','\\n'))
    except Exception as e:
        print('ERROR:', type(e).__name__, str(e))