from urllib import request, parse
import http.cookiejar, re, csv, io
from bs4 import BeautifulSoup
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar(); op=request.build_opener(request.HTTPCookieProcessor(cj))
# login
post=parse.urlencode({'next':'/orders','sso':'company'}).encode()
op.open(request.Request(base+'/login', data=post, method='POST'), timeout=10).read()
params={'from':'2026-09-01','to':'2026-09-30','status':'Open','sort':'OrderID','dir':'asc'}
url=base+'/orders?'+parse.urlencode(params)
html=op.open(url, timeout=10).read().decode('utf-8','replace')
print('URL', url)
print(re.search(r"Total:.*?</p>", html, re.S).group(0))
soup=BeautifulSoup(html,'html.parser')
headers=[th.get_text(strip=True) for th in soup.select('#results th')]
print('headers', headers)
for tr in soup.select('#results tbody tr')[:3]:
    print([td.get_text(strip=True) for td in tr.select('td')])
print('pager links', [a.get('href') for a in soup.select('.pager a')])
exp=soup.select_one('#export-csv').get('href')
print('export href', exp)
expdata=op.open(base+exp, timeout=10).read().decode('utf-8-sig','replace')
print('export first 500:', expdata[:500])
r=list(csv.DictReader(io.StringIO(expdata)))
print('export rows', len(r), 'fieldnames', r[0].keys() if r else None)
print('first', r[0] if r else None, 'last', r[-1] if r else None)
# detail sample
detail_url=base+'/orders/'+r[0]['OrderID']
html=op.open(detail_url, timeout=10).read().decode('utf-8','replace')
print('\ndetail url', detail_url, 'len', len(html))
print(html[:3000])