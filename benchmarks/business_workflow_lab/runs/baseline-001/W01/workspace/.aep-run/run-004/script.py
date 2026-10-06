from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar
base='http://127.0.0.1:8810'
opener=build_opener(HTTPCookieProcessor(CookieJar()))
data=urlencode({'username':'lab.analyst','password':'Lab#2026','next':'/orders'}).encode()
req=Request(base+'/login', data=data, headers={'Content-Type':'application/x-www-form-urlencoded'})
with opener.open(req, timeout=10) as resp:
    print('POST', resp.status, resp.geturl())
    text=resp.read().decode('utf-8')
print(text[:5000])
