from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar
base='http://127.0.0.1:8810'
opener=build_opener(HTTPCookieProcessor(CookieJar()))
# login
post=urlencode({'username':'lab.analyst','password':'Lab#2026'}).encode()
opener.open(Request(base+'/login', data=post, headers={'Content-Type':'application/x-www-form-urlencoded'}), timeout=5).read()
for qs in ['from=2026-09-01&to=2026-09-30','date_from=2026-09-01&date_to=2026-09-30','from=2026-09-01&to=2026-09-30&sort=InvoiceID&dir=asc']:
    url=base+'/invoices/export.csv?'+qs
    r=opener.open(url, timeout=5); data=r.read()
    print('\nQS', qs, 'status', r.status, 'ctype', r.headers.get('content-type'), 'len', len(data))
    print(data.decode('utf-8-sig','replace')[:2000])
