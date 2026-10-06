from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode, urljoin
from http.cookiejar import CookieJar
base='http://127.0.0.1:8810/'
cj=CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))
def open_url(path, data=None):
    url=urljoin(base,path)
    r=opener.open(Request(url, data=urlencode(data).encode() if data else None, method='POST' if data else 'GET'), timeout=10)
    txt=r.read().decode('utf-8', errors='replace')
    print('\nURL', r.geturl(), 'status', r.status, 'len', len(txt))
    print(txt[:5000])
    return txt,r.geturl()
open_url('/login', {'next':'/orders/0045000109','sso':'company'})
html,url=open_url('/orders/0045000109')
if '<h1>Sign in' in html:
    open_url('/login', {'next':'/orders/0045000109','sso':'company'})
    html,url=open_url('/orders/0045000109')
print('--- FULL-ish ---')
print(html[:10000])
