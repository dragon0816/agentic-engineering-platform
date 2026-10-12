from pathlib import Path
from urllib.request import urlopen

workspace = Path.cwd()
print('WORKSPACE', workspace)
for sub in ['input','output']:
    p = workspace / sub
    print(sub, 'exists=', p.exists())
    if p.exists():
        print(sub, 'files=', [x.name for x in sorted(p.iterdir())])

urls = [
    'http://127.0.0.1:64493/t12/a',
    'http://127.0.0.1:64493/t12/b',
    'http://127.0.0.1:64493/t12/c',
]
for url in urls:
    print('\nURL', url)
    with urlopen(url, timeout=10) as r:
        data = r.read()
        ctype = r.headers.get('content-type')
    text = data.decode('utf-8', errors='replace')
    print('content-type:', ctype)
    print('bytes:', len(data))
    print('sample:')
    print(text[:1200])
