from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar
import csv, io, re
base='http://127.0.0.1:8810'
op=build_opener(HTTPCookieProcessor(CookieJar()))
op.open(Request(base+'/login', data=urlencode({'next':'/orders','sso':'company'}).encode(), method='POST'), timeout=10).read()
for path, params in [('/orders',{'from':'2026-09-01','to':'2026-09-30'}),('/orders',{'from':'2026-09-01','to':'2026-09-30','status':'Open'}),('/orders',{'date_from':'2026-09-01','date_to':'2026-09-30'}),('/invoices',{'from':'2026-09-01','to':'2026-09-30'})]:
    url=base+path+'?'+urlencode(params)
    html=op.open(url, timeout=10).read().decode('utf-8','replace')
    m=re.search(r'Total: <strong>(\d+)</strong>', html)
    print(path, params, 'count', m.group(1) if m else None)
    ex=re.search(r"id='export-csv' href='([^']+)'", html)
    print(' export', ex.group(1) if ex else None)
    print(' inputs', re.findall(r"name='(from|to|status)'[^>]*value='([^']*)'", html)[:5])
# download exports
for name,path,params in [('orders','/orders/export.csv',{'from':'2026-09-01','to':'2026-09-30'}),('invoices','/invoices/export.csv',{'from':'2026-09-01','to':'2026-09-30'})]:
    data=op.open(base+path+'?'+urlencode(params), timeout=10).read().decode('utf-8-sig')
    print('\nEXPORT', name, len(data), data.splitlines()[0])
    rdr=list(csv.DictReader(io.StringIO(data)))
    print('rows', len(rdr), 'sample', rdr[:3])
    if name=='orders': print('statuses', sorted(set(r['Status'] for r in rdr)))
