from pathlib import Path
import urllib.request, urllib.parse, http.cookiejar
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar()
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

def get(path):
    with opener.open(base+path, timeout=10) as r:
        return r.geturl(), r.status, r.read().decode('utf-8', errors='replace')

def post(path,data):
    d=urllib.parse.urlencode(data).encode()
    req=urllib.request.Request(base+path, data=d, method='POST')
    with opener.open(req, timeout=10) as r:
        return r.geturl(), r.status, r.read().decode('utf-8', errors='replace')
for path in ['/', '/login']:
    try:
        url,st,html=get(path); print('GET',path,st,url); print(html[:1000])
    except Exception as e: print('ERR', path, repr(e))
try:
    url,st,html=post('/login', {'username':'lab.analyst','password':'Lab#2026'})
    print('POST login',st,url); print(html[:1500])
    Path('output/workflow').mkdir(parents=True, exist_ok=True)
    Path('output/workflow/login_page.html').write_text(html, encoding='utf-8')
    for path in ['/sales-orders','/sales_orders','/orders','/sales-orders?customer_id=C001&date_from=2026-08-01&date_to=2026-10-31']:
        try:
            url,st,html=get(path); print('\nGET',path,st,url); print(html[:2000]); Path('output/workflow/'+path.strip('/').split('?')[0].replace('/','_')+'.html').write_text(html,encoding='utf-8')
        except Exception as e: print('ERR get', path, repr(e))
except Exception as e: print('LOGIN ERR', repr(e))