from pathlib import Path
from urllib.request import urlopen, Request

workspace = Path.cwd()
print('Workspace:', workspace)
print('Input files:')
input_dir = workspace / 'input'
if input_dir.exists():
    for p in sorted(input_dir.iterdir()):
        print(' -', p.name, 'dir' if p.is_dir() else f'{p.stat().st_size} bytes')
else:
    print(' - input directory does not exist')

url = 'http://127.0.0.1:63668/t11/list'
print('\nFetching list URL:', url)
req = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urlopen(req, timeout=10) as resp:
    data = resp.read()
    print('Status:', getattr(resp, 'status', 'unknown'))
    print('Content-Type:', resp.headers.get('Content-Type'))
    text = data.decode(resp.headers.get_content_charset() or 'utf-8', errors='replace')
print('Page length:', len(text))
print('First 2000 chars of markup:')
print(text[:2000])