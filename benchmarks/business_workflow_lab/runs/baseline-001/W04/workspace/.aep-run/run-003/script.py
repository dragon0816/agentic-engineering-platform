from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar
base='http://127.0.0.1:8810'
cj=CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))
def get(path):
    return opener.open(base+path).read().decode('utf-8','replace')
def post(path,data):
    req=Request(base+path, data=urlencode(data).encode(), headers={'Content-Type':'application/x-www-form-urlencoded'})
    return opener.open(req).read().decode('utf-8','replace')
try:
    txt=get('/login')
    print('login ok', txt[:1200])
    txt=post('/login', {'username':'lab.analyst','password':'Lab#2026'})
    print('after login', txt[:2000])
    import re
    print('links', re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', txt, re.S)[:20])
    for path in ['/sales-orders','/sales_orders','/orders','/sales','/customers','/invoices']:
        try:
            t=get(path)
            print('\nPATH',path, 'len',len(t), t[:500])
        except Exception as e:
            print('ERR', path, e)
except Exception as e:
    print('top error', type(e), e)
