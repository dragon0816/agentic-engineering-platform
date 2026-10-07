from pathlib import Path
import urllib.request

workspace = Path.cwd()
print('workspace:', workspace)
print('input files:')
inp = workspace / 'input'
if inp.exists():
    for p in sorted(inp.rglob('*')):
        print(' -', p.relative_to(workspace), 'dir' if p.is_dir() else f'{p.stat().st_size} bytes')
else:
    print(' input folder missing')

url = 'http://127.0.0.1:50351/t13/list'
print('\nFetching list URL:', url)
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        print('status:', r.status)
        print('content-type:', r.headers.get('content-type'))
        data = r.read(2000)
        print('first 2000 bytes:')
        print(data.decode('utf-8', errors='replace'))
except Exception as e:
    print('fetch error:', type(e).__name__, str(e))