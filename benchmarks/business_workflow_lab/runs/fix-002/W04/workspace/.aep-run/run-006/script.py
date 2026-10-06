from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode, urljoin
from http.cookiejar import CookieJar
from html.parser import HTMLParser
import csv, io
base='http://127.0.0.1:8810/'
cj=CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))

def open_url(path, data=None):
    url=urljoin(base,path)
    req=Request(url, data=urlencode(data).encode() if data else None, method='POST' if data else 'GET')
    r=opener.open(req, timeout=10)
    body=r.read()
    txt=body.decode('utf-8', errors='replace')
    print('\nURL', r.geturl(), 'status', r.status, 'ctype', r.headers.get('content-type'), 'len', len(body))
    print(txt[:1000])
    return txt,r
open_url('/login', {'next':'/orders','sso':'company'})
html,r=open_url('/orders?'+urlencode({'from':'2026-09-01','to':'2026-09-30','status':'Open','sort':'OrderDate','dir':'asc'}))
print('has result count', 'result-count' in html, 'login', '<h1>Sign in' in html)
# If login, login next and retry
if '<h1>Sign in' in html:
    open_url('/login', {'next':'/orders?'+urlencode({'from':'2026-09-01','to':'2026-09-30','status':'Open','sort':'OrderDate','dir':'asc'}),'sso':'company'})
# export
path='/orders/export.csv?'+urlencode({'from':'2026-09-01','to':'2026-09-30','status':'Open','sort':'OrderDate','dir':'asc'})
txt,r=open_url(path)
if '<h1>Sign in' in txt:
    open_url('/login', {'next':path,'sso':'company'})
    txt,r=open_url(path)
print('export first', txt[:500])
try:
    for i,row in enumerate(csv.reader(io.StringIO(txt))):
        print('csv',i,row)
        if i>5: break
except Exception as e: print('csv err',e)
