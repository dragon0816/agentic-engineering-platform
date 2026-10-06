from pathlib import Path
import requests
from bs4 import BeautifulSoup
base='http://127.0.0.1:8810'
s=requests.Session()
r=s.get(base+'/login', timeout=10)
print('login status', r.status_code, r.url)
print(r.text[:1000])
# parse login form
soup=BeautifulSoup(r.text,'html.parser')
print('forms', len(soup.find_all('form')))
for f in soup.find_all('form'):
    print('form action', f.get('action'), 'method', f.get('method'))
    for inp in f.find_all(['input','select','button']):
        print(inp.name, inp.get('name'), inp.get('id'), inp.get('value'), inp.text.strip())
