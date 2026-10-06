from urllib.request import urlopen
from urllib.parse import urljoin
from html.parser import HTMLParser
import re, json

base='http://127.0.0.1:64664/t11/list'
html=urlopen(base, timeout=10).read().decode('utf-8','replace')
print('LIST length', len(html))
print(html[:2000])

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(); self.links=[]
    def handle_starttag(self, tag, attrs):
        if tag.lower()=='a':
            d=dict(attrs); href=d.get('href')
            if href: self.links.append(urljoin(base, href))

p=LinkParser(); p.feed(html)
links=[]
for u in p.links:
    if u not in links:
        links.append(u)
print('links', links)
for u in links[:5]:
    h=urlopen(u, timeout=10).read().decode('utf-8','replace')
    print('\nURL',u,'len',len(h))
    print(h[:2500])
