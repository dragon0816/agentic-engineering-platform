from pathlib import Path
from urllib.request import urlopen

urls = [
    'http://127.0.0.1:64212/t12/a',
    'http://127.0.0.1:64212/t12/b',
    'http://127.0.0.1:64212/t12/c',
]
print('Workspace:', Path.cwd())
print('Input files:')
input_dir = Path('input')
if input_dir.exists():
    for p in sorted(input_dir.iterdir()):
        print(' -', p.name, 'size=', p.stat().st_size)
else:
    print(' - input directory not found')

for url in urls:
    print('\nURL:', url)
    with urlopen(url, timeout=10) as resp:
        content_type = resp.headers.get('Content-Type')
        data = resp.read()
    print('Content-Type:', content_type)
    print('Bytes:', len(data))
    text = data.decode('utf-8', errors='replace')
    print('Sample:')
    print(text[:1200])
