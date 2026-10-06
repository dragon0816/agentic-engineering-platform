from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode, urljoin
from http.cookiejar import CookieJar
from html.parser import HTMLParser
base='http://127.0.0.1:8810/'
cj=CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))
def req(path, data=None):
    url=urljoin(base,path)
    if data is not None:
        body=urlencode(data).encode(); r=opener.open(Request(url, data=body, method='POST'), timeout=10)
    else:
        r=opener.open(url, timeout=10)
    txt=r.read().decode('utf-8', errors='replace')
    print('\n===', 'POST' if data else 'GET', path, '=>', r.geturl(), r.status, '===')
    print(txt[:5000])
    print('cookies', [(c.name,c.value) for c in cj])
    return txt, r.geturl()
req('/')
req('/login', {'next':'/orders','sso':'company'})
html,_=req('/orders?date_from=2026-09-01&date_to=2026-09-30&status=Open&sort=OrderDate&order=asc')
