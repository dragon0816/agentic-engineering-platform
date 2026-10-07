import os, urllib.request
from html.parser import HTMLParser

workspace = os.getcwd()
print('workspace:', workspace)
print('input files:')
for root, dirs, files in os.walk('input'):
    for f in files:
        p = os.path.join(root, f)
        print(' -', p, os.path.getsize(p), 'bytes')

url = 'http://127.0.0.1:63795/t11/list'
print('\nFetching list URL:', url)
with urllib.request.urlopen(url, timeout=10) as r:
    data = r.read()
    ctype = r.headers.get('Content-Type')
print('content-type:', ctype)
html = data.decode('utf-8', errors='replace')
print('list html length:', len(html))
print('list html sample:')
print(html[:2000])

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower() == 'a':
            d = dict(attrs)
            self.links.append((d.get('href',''), d))

parser = LinkParser()
parser.feed(html)
print('\nlinks found:')
for href, attrs in parser.links[:50]:
    print(' -', href, attrs)
