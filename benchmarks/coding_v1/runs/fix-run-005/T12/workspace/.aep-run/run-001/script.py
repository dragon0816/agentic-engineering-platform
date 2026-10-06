from pathlib import Path
from urllib.request import urlopen

workspace = Path.cwd()
print('WORKSPACE', workspace)
print('INPUT FILES:')
for p in sorted((workspace/'input').glob('*')):
    print('-', p.name, 'size=', p.stat().st_size)

urls = ['http://127.0.0.1:49758/t12/a','http://127.0.0.1:49758/t12/b','http://127.0.0.1:49758/t12/c']
for url in urls:
    print('\nURL:', url)
    with urlopen(url, timeout=10) as resp:
        data = resp.read(2000)
        print('status:', resp.status, 'content-type:', resp.headers.get('content-type'))
        print(data.decode('utf-8', errors='replace')[:1500])
