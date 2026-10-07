from pathlib import Path
from urllib.request import urlopen

ws = Path.cwd()
print('workspace:', ws)
print('input files:')
inp = ws / 'input'
if inp.exists():
    for p in sorted(inp.rglob('*')):
        print(' -', p.relative_to(ws), 'dir' if p.is_dir() else f'{p.stat().st_size} bytes')
else:
    print(' input folder missing')

url = 'http://127.0.0.1:50351/t11/list'
print('\nFetching list URL:', url)
with urlopen(url, timeout=10) as r:
    content = r.read()
    ctype = r.headers.get('content-type')
print('status content-type:', ctype)
text = content.decode('utf-8', errors='replace')
print('page length:', len(text))
print('page markup sample:')
print(text[:3000])