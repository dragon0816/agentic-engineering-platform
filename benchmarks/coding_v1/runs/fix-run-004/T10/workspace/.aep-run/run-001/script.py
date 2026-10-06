from pathlib import Path
import os, sys, urllib.request

ws = Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').glob('*')):
    print('-', p.name, 'size', p.stat().st_size)
notes = ws/'input'/'catalog_notes.md'
if notes.exists():
    print('\n--- catalog_notes.md ---')
    print(notes.read_text(encoding='utf-8'))

url='http://127.0.0.1:58649/t10/catalog'
print('\n--- URL sample ---')
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        print('status:', resp.status)
        print('content-type:', resp.headers.get('content-type'))
        html = resp.read(5000).decode('utf-8', errors='replace')
        print(html)
except Exception as e:
    print('ERROR fetching URL:', repr(e))
