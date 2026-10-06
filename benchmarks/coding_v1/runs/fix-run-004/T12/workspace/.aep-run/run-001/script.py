from pathlib import Path
from urllib.request import urlopen

print('Workspace:', Path.cwd())
print('Input files:')
for p in sorted(Path('input').glob('**/*')):
    print(' -', p, 'file' if p.is_file() else 'dir')

urls = [
    'http://127.0.0.1:58649/t12/a',
    'http://127.0.0.1:58649/t12/b',
    'http://127.0.0.1:58649/t12/c',
]
for url in urls:
    print('\n--- URL:', url)
    with urlopen(url, timeout=10) as r:
        data = r.read(2000)
        print('status:', getattr(r, 'status', None), 'content-type:', r.headers.get('content-type'))
        text = data.decode('utf-8', errors='replace')
        print(text[:1500])
