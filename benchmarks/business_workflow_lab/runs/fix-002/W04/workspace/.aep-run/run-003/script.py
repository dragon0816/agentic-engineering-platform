from pathlib import Path
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode, urljoin
from http.cookiejar import CookieJar
base='http://127.0.0.1:8810/'
cj=CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))
def get(url):
    r=opener.open(url, timeout=10)
    data=r.read().decode('utf-8', errors='replace')
    print('URL', r.geturl(), 'STATUS', r.status, 'CTYPE', r.headers.get('content-type'))
    print(data[:4000])
    print('COOKIES', [(c.name,c.value) for c in cj])
    return data, r.geturl()
get(base)
