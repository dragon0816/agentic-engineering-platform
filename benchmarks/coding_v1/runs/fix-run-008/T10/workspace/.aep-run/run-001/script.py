import os, pathlib, urllib.request
from html.parser import HTMLParser

ws = pathlib.Path.cwd()
print('workspace:', ws)
print('input files:')
for p in sorted((ws/'input').iterdir()):
    print(' -', p.name, 'size=', p.stat().st_size)
    if p.name.lower().endswith(('.md','.txt','.csv','.html')):
        txt = p.read_text(encoding='utf-8', errors='replace')
        print('--- first 1200 chars of', p.name, '---')
        print(txt[:1200])
        print('--- end preview ---')

url = 'http://127.0.0.1:64650/t10/catalog'
print('fetching:', url)
with urllib.request.urlopen(url, timeout=10) as r:
    html = r.read().decode('utf-8', errors='replace')
print('status ok, chars:', len(html))
print('--- catalog html first 3000 chars ---')
print(html[:3000])
print('--- end catalog preview ---')
