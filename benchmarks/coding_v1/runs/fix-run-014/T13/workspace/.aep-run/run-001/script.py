import os, json, urllib.request
from pathlib import Path

ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
inp = ws/'input'
if inp.exists():
    for p in sorted(inp.rglob('*')):
        print(' -', p.relative_to(ws), 'file' if p.is_file() else 'dir')
else:
    print('input folder missing')

url = 'http://127.0.0.1:63668/t13/list'
print('\nFETCH LIST:', url)
try:
    with urllib.request.urlopen(url, timeout=10) as resp:
        body = resp.read(5000)
        print('status', resp.status)
        print('content-type', resp.headers.get('Content-Type'))
        text = body.decode('utf-8', errors='replace')
        print('MARKUP SAMPLE START')
        print(text[:3000])
        print('MARKUP SAMPLE END')
except Exception as e:
    print('FETCH ERROR', type(e).__name__, str(e))
