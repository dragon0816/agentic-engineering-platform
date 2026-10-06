import urllib.request, urllib.parse, http.cookiejar, re
from pathlib import Path
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(path, data=None):
    if data is not None:
        data=urllib.parse.urlencode(data).encode()
    r=opener.open(base+path, data=data, timeout=10)
    body=r.read().decode('utf-8', errors='replace')
    print('\nURL', r.geturl(), 'status', r.status)
    print('cookies', [(c.name,c.value) for c in cj])
    print(body[:5000])
    return body
req('/')
body=req('/login', {'next':'/orders','sso':'company'})
body=req('/orders')
print('forms/links snippets:')
for m in re.finditer(r'<form.*?</form>', body, flags=re.S): print(m.group(0)[:2000])
print('links', re.findall(r'href=["\']([^"\']+)', body)[:50])
body=req('/orders?customer_id=C001&date_from=2026-08-01&date_to=2026-10-31')
print('links filtered', re.findall(r'href=["\']([^"\']+)', body)[:50])