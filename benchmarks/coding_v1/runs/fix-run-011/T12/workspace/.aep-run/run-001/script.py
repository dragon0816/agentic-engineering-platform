from urllib.request import urlopen
from pathlib import Path
urls = [
    'http://127.0.0.1:54763/t12/a',
    'http://127.0.0.1:54763/t12/b',
    'http://127.0.0.1:54763/t12/c',
]
print('Workspace:', Path.cwd())
print('Input files:')
input_dir = Path('input')
if input_dir.exists():
    for p in sorted(input_dir.iterdir()):
        print(' -', p.name, 'size=', p.stat().st_size)
else:
    print(' (no input dir)')
for url in urls:
    print('\nURL:', url)
    with urlopen(url, timeout=10) as resp:
        data = resp.read().decode(resp.headers.get_content_charset() or 'utf-8', errors='replace')
        print('Status:', getattr(resp, 'status', 'unknown'), 'Content-Type:', resp.headers.get('content-type'))
        print('Markup sample:')
        print(data[:2000])
        print('--- end sample ---')
