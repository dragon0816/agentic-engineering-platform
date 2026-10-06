from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar
import re
base='http://127.0.0.1:8810'
cj=CookieJar(); op=build_opener(HTTPCookieProcessor(cj))
# login
req=Request(base+'/login', data=urlencode({'next':'/orders','sso':'company'}).encode(), method='POST')
resp=op.open(req, timeout=10)
print('login', resp.status, resp.geturl())
html=resp.read().decode('utf-8','replace')
print(html[:1000])
for path in ['/orders','/invoices']:
    qs=urlencode({'date_from':'2026-09-01','date_to':'2026-09-30'})
    url=base+path+'?'+qs
    resp=op.open(url, timeout=10); html=resp.read().decode('utf-8','replace')
    print('\nPAGE', path, resp.status, resp.geturl())
    print(html[:3000])
    print('hrefs', re.findall(r'href=["\']([^"\']+)', html)[:20])
    print('forms', re.findall(r'<form.*?</form>', html, flags=re.S)[:2])
