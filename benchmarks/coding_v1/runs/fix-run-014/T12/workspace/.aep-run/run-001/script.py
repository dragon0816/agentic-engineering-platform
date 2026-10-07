from pathlib import Path
from urllib.request import urlopen

workspace = Path.cwd()
print('workspace:', workspace)
print('input files:', [p.name for p in (workspace/'input').glob('*')])
print('output exists:', (workspace/'output').exists())
urls = [
    'http://127.0.0.1:63668/t12/a',
    'http://127.0.0.1:63668/t12/b',
    'http://127.0.0.1:63668/t12/c',
]
for url in urls:
    print('\nURL:', url)
    with urlopen(url, timeout=10) as r:
        data = r.read()
        print('status:', getattr(r, 'status', 'unknown'))
        print('content-type:', r.headers.get('content-type'))
        text = data.decode('utf-8', errors='replace')
        print('length:', len(text))
        print('sample:', text[:1000].replace('\n', '\\n'))
