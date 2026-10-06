from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar
import re, csv, io
base='http://127.0.0.1:8810'
cj=CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))
def open_url(path, data=None):
    if data is None:
        return opener.open(base+path).read().decode('utf-8','replace')
    req=Request(base+path, data=urlencode(data).encode(), headers={'Content-Type':'application/x-www-form-urlencoded'})
    return opener.open(req).read().decode('utf-8','replace')
def login():
    open_url('/login')
    return open_url('/login', {'username':'lab.analyst','password':'Lab#2026'})
def get_auth(path):
    t=open_url(path)
    if '<title>Sign in' in t or "<h1>Sign in" in t:
        print('relogin for', path)
        login()
        t=open_url(path)
    return t
login()
path='/orders?'+urlencode({'from':'2026-09-01','to':'2026-09-30','status':'Open'})
t=get_auth(path)
print('orders page len', len(t))
print(t[:2500])
print('total match', re.findall(r'Total:\s*([0-9]+)', t))
export='/orders/export.csv?'+urlencode({'from':'2026-09-01','to':'2026-09-30','status':'Open'})
csvtxt=get_auth(export)
print('csv len', len(csvtxt))
print(csvtxt[:1000])
