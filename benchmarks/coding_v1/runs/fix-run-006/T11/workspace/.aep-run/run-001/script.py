from pathlib import Path
from urllib.request import urlopen

print('Workspace:', Path.cwd())
print('Input files:')
for p in sorted(Path('input').glob('**/*')):
    print(' -', p, 'file' if p.is_file() else 'dir')
url='http://127.0.0.1:56996/t11/list'
print('\nFetching list URL:', url)
with urlopen(url, timeout=10) as r:
    data=r.read()
    print('Status:', getattr(r, 'status', 'unknown'))
    print('Content-Type:', r.headers.get('content-type'))
    text=data.decode(r.headers.get_content_charset() or 'utf-8', errors='replace')
print('Length:', len(text))
print('First 2000 chars:\n', text[:2000])