import os, urllib.request
from html.parser import HTMLParser
base='http://127.0.0.1:57997/t11/list'
print('CWD', os.getcwd())
print('input exists', os.path.isdir('input'), 'files', os.listdir('input') if os.path.isdir('input') else [])
print('output exists', os.path.isdir('output'), 'files', os.listdir('output') if os.path.isdir('output') else [])
try:
    with urllib.request.urlopen(base, timeout=10) as r:
        data=r.read()
        print('list status', r.status, 'content-type', r.headers.get('content-type'), 'bytes', len(data))
        text=data.decode('utf-8', errors='replace')
        print('list snippet:')
        print(text[:2000])
except Exception as e:
    print('FETCH ERROR', type(e).__name__, str(e))
