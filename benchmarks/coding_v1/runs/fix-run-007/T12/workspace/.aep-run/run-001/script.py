from pathlib import Path
import urllib.request

workspace = Path.cwd()
print('workspace:', workspace)
print('input files:', [p.name for p in (workspace/'input').glob('*')])
print('output exists:', (workspace/'output').exists())
urls = [
    'http://127.0.0.1:57997/t12/a',
    'http://127.0.0.1:57997/t12/b',
    'http://127.0.0.1:57997/t12/c',
]
for url in urls:
    print('\nURL:', url)
    with urllib.request.urlopen(url, timeout=10) as resp:
        data = resp.read()
        print('status:', resp.status, 'content-type:', resp.headers.get('Content-Type'), 'bytes:', len(data))
        text = data.decode(resp.headers.get_content_charset() or 'utf-8', errors='replace')
        print(text[:1000])