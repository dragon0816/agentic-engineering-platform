from pathlib import Path
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode, urljoin
from http.cookiejar import CookieJar
base='http://127.0.0.1:8810'
cj=CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))
def get(url):
    with opener.open(url, timeout=10) as resp:
        return resp.geturl(), resp.status, resp.read().decode('utf-8')
url,status,text=get(base+'/login')
print('GET',status,url)
print(text[:3000])
