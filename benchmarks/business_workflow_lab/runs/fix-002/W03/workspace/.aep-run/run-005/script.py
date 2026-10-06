from pathlib import Path
import urllib.request, urllib.parse, http.cookiejar, csv, io
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar(); opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
opener.open(urllib.request.Request(base+'/login', data=urllib.parse.urlencode({'next':'/invoices','sso':'company'}).encode(), method='POST'), timeout=10).read()
for params in [ {'from':'2026-09-01','to':'2026-09-30'}, {'date_from':'2026-09-01','date_to':'2026-09-30'} ]:
    url=base+'/invoices/export.csv?'+urllib.parse.urlencode(params)
    with opener.open(url, timeout=10) as r:
        text=r.read().decode('utf-8-sig')
    rows=list(csv.DictReader(io.StringIO(text)))
    dates=sorted({row['InvoiceDate'] for row in rows})
    print(params, 'rows', len(rows), 'date range', dates[:3], dates[-3:] if dates else [])
    print(text.splitlines()[:3])
