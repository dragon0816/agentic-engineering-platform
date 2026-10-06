from urllib import request, parse
import http.cookiejar, re, csv, io
from html.parser import HTMLParser
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar(); op=request.build_opener(request.HTTPCookieProcessor(cj))
post=parse.urlencode({'next':'/orders','sso':'company'}).encode()
op.open(request.Request(base+'/login', data=post, method='POST'), timeout=10).read()
params={'from':'2026-09-01','to':'2026-09-30','status':'Open','sort':'OrderID','dir':'asc'}
url=base+'/orders?'+parse.urlencode(params)
html=op.open(url, timeout=10).read().decode('utf-8','replace')
print('URL', url)
m=re.search(r"<p id='result-count'>(.*?)</p>", html, re.S); print('count', re.sub('<.*?>','',m.group(1)) if m else None)
print('table snippet')
mt=re.search(r"<table id='results'.*?</table>", html, re.S); print(mt.group(0)[:2000] if mt else 'no table')
print('pager links', re.findall(r"href='([^']+page=\d+[^']*)'", html))
exp=re.search(r"id='export-csv' href='([^']+)'", html).group(1)
print('export href', exp)
expdata=op.open(base+exp, timeout=10).read().decode('utf-8-sig','replace')
print('export first 500:', expdata[:500])
r=list(csv.DictReader(io.StringIO(expdata)))
print('export rows', len(r), 'fieldnames', r[0].keys() if r else None)
print('first', r[0] if r else None, 'last', r[-1] if r else None)
# detail sample
html=op.open(base+'/orders/'+r[0]['OrderID'], timeout=10).read().decode('utf-8','replace')
print('\ndetail snippet')
print(html[:5000])