from pathlib import Path
from urllib.request import urlopen, Request
from urllib.parse import urljoin
from html.parser import HTMLParser

ws = Path.cwd()
print('WORKSPACE', ws)
print('INPUT FILES:')
inp = ws/'input'
if inp.exists():
    for p in sorted(inp.rglob('*')):
        print(' -', p.relative_to(ws), 'dir' if p.is_dir() else f'{p.stat().st_size} bytes')
else:
    print(' input folder missing')

url = 'http://127.0.0.1:54763/t11/list'
print('\nFETCH LIST:', url)
html = urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=10).read().decode('utf-8', errors='replace')
print('LIST HTML LENGTH', len(html))
print('LIST HTML SAMPLE:')
print(html[:2000])

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]; self._a=None
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='a':
            d=dict(attrs); self._a={'href':d.get('href',''), 'text':''}
    def handle_data(self, data):
        if self._a is not None: self._a['text'] += data
    def handle_endtag(self, tag):
        if tag.lower()=='a' and self._a is not None:
            self.links.append(self._a); self._a=None

lp=LinkParser(); lp.feed(html)
print('\nLINKS:')
for l in lp.links[:20]:
    print(l['text'].strip(), '=>', urljoin(url, l['href']))

if lp.links:
    detail_url = urljoin(url, lp.links[0]['href'])
    print('\nFETCH FIRST DETAIL:', detail_url)
    dh = urlopen(Request(detail_url, headers={'User-Agent':'Mozilla/5.0'}), timeout=10).read().decode('utf-8', errors='replace')
    print('DETAIL HTML LENGTH', len(dh))
    print('DETAIL HTML SAMPLE:')
    print(dh[:2500])
