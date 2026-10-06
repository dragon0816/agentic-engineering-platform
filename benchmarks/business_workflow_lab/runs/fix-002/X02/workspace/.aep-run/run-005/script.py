from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode
import http.cookiejar
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))
# get login for cookie maybe
opener.open(Request(base+'/', headers={'User-Agent':'Mozilla/5.0'}), timeout=5).read()
body=urlencode({'next':'/orders','sso':'company'}).encode()
r=opener.open(Request(base+'/login', data=body, headers={'User-Agent':'Mozilla/5.0','Content-Type':'application/x-www-form-urlencoded'}), timeout=5)
print('login final', r.geturl(), r.status)
print(r.read().decode('utf-8','replace')[:1000])
for path in ['/orders','/invoices']:
    url=base+path+'?'+urlencode({'customer':'C001','date_from':'2026-09-01','date_to':'2026-09-30'})
    r=opener.open(Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=5)
    txt=r.read().decode('utf-8','replace')
    print('\nURL', r.geturl(), r.status)
    print(txt[:3000])
