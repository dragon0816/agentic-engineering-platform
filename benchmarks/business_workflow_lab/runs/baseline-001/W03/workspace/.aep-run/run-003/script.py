from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar
base='http://127.0.0.1:8810'
cj=CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))
def get(path):
    r=opener.open(base+path, timeout=5); data=r.read(); return r, data
try:
    r,data=get('/login')
    print('login status', r.status, r.geturl())
    print(data.decode('utf-8','replace')[:2000])
    post=urlencode({'username':'lab.analyst','password':'Lab#2026'}).encode()
    req=Request(base+'/login', data=post, headers={'Content-Type':'application/x-www-form-urlencoded'})
    r=opener.open(req, timeout=5); data=r.read()
    print('post status', r.status, r.geturl())
    print(data.decode('utf-8','replace')[:2000])
    for path in ['/invoices','/invoices?date_from=2026-09-01&date_to=2026-09-30','/invoices?Date%20from=2026-09-01&Date%20to=2026-09-30']:
        r,data=get(path)
        print('\nPATH', path, r.status, r.geturl(), r.headers.get('content-type'))
        txt=data.decode('utf-8','replace')
        print(txt[:3000])
except Exception as e:
    print('ERR', type(e), e)
