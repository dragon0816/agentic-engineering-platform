import os, json, urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin

ws=os.getcwd()
print('workspace', ws)
for root, dirs, files in os.walk('input'):
    print('input_dir', root, 'files', files[:20])

url='http://127.0.0.1:64650/t13/list'
try:
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=10) as resp:
        data=resp.read()
        print('list_status', resp.status, resp.getheader('Content-Type'), 'bytes', len(data))
        text=data.decode(resp.headers.get_content_charset() or 'utf-8', errors='replace')
        print('list_sample')
        print(text[:2000])
except Exception as e:
    print('list_fetch_error', repr(e))
