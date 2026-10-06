from pathlib import Path
import urllib.request, urllib.parse, http.cookiejar, re
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
# login
req=urllib.request.Request(base+'/login', data=urllib.parse.urlencode({'next':'/invoices','sso':'company'}).encode(), method='POST')
with opener.open(req, timeout=10) as r:
    print('login', r.status, r.geturl())
# get invoices filtered
params=urllib.parse.urlencode({'date_from':'2026-09-01','date_to':'2026-09-30'})
url=base+'/invoices?'+params
with opener.open(url, timeout=10) as r:
    html=r.read().decode('utf-8', errors='replace')
    print('page', r.status, r.geturl(), len(html))
    print(html[:3000])
    print('links', re.findall(r'href=["\']([^"\']+)', html)[:20])
