from pathlib import Path
from urllib.request import urlopen

urls = [
    'http://127.0.0.1:50447/t12/a',
    'http://127.0.0.1:50447/t12/b',
    'http://127.0.0.1:50447/t12/c',
]
print('Workspace:', Path.cwd())
print('Input files:', [p.name for p in Path('input').glob('*')] if Path('input').exists() else 'no input folder')
for url in urls:
    print('\n=== URL:', url, '===')
    with urlopen(url, timeout=10) as resp:
        body = resp.read().decode('utf-8', errors='replace')
        print('status:', resp.status)
        print('content-type:', resp.headers.get('content-type'))
        print('first 2000 chars:')
        print(body[:2000])
