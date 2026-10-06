from pathlib import Path
import requests
from bs4 import BeautifulSoup
base='http://127.0.0.1:8810'
s=requests.Session()
r=s.get(base+'/login')
print('login status', r.status_code, r.url)
print(r.text[:1000])
# login
r=s.post(base+'/login', data={'username':'lab.analyst','password':'Lab#2026'}, allow_redirects=True)
print('post status', r.status_code, r.url)
print(r.text[:1500])
# find links
soup=BeautifulSoup(r.text,'html.parser')
for a in soup.find_all('a'):
    print('link', a.get_text(strip=True), a.get('href'))
# sales page possible
for path in ['/sales-orders','/sales_orders','/orders','/sales']:
    rr=s.get(base+path)
    print('\nPATH',path, rr.status_code, rr.url, rr.text[:300])
