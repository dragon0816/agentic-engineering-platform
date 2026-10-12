import os, urllib.request
from pathlib import Path
workspace=Path.cwd()
print('cwd=', workspace)
print('input files:')
for p in sorted((workspace/'input').glob('**/*')):
    print('-', p.relative_to(workspace), 'file' if p.is_file() else 'dir', p.stat().st_size if p.is_file() else '')
url='http://127.0.0.1:50447/t13/list'
print('\nFetching list page:', url)
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data=r.read()
        print('status=', r.status)
        print('content-type=', r.headers.get('Content-Type'))
        print('bytes=', len(data))
        text=data.decode('utf-8', errors='replace')
        print('--- page markup sample start ---')
        print(text[:4000])
        print('--- page markup sample end ---')
except Exception as e:
    print('fetch error:', type(e).__name__, str(e))