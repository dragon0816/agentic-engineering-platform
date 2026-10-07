import os, json, urllib.request
from pathlib import Path

workspace = Path.cwd()
print('workspace:', workspace)
print('input exists:', (workspace/'input').exists())
print('output exists:', (workspace/'output').exists())
print('input files:')
if (workspace/'input').exists():
    for p in sorted((workspace/'input').iterdir()):
        print(' -', p.name, 'file' if p.is_file() else 'dir')

urls = [
    'http://127.0.0.1:64650/t12/a',
    'http://127.0.0.1:64650/t12/b',
    'http://127.0.0.1:64650/t12/c',
]
for url in urls:
    print('\nURL:', url)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = r.read()
            print('status:', getattr(r, 'status', None), 'content-type:', r.headers.get('Content-Type'), 'bytes:', len(data))
            text = data.decode(r.headers.get_content_charset() or 'utf-8', errors='replace')
            print(text[:2000])
    except Exception as e:
        print('ERROR:', repr(e))
