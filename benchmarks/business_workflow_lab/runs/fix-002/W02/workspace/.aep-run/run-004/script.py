import urllib.request, urllib.parse, http.cookiejar, re, csv, io
from html.parser import HTMLParser
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar(); opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def openp(path, data=None):
    if data is not None: data=urllib.parse.urlencode(data).encode()
    r=opener.open(base+path, data=data, timeout=10)
    return r.geturl(), r.read().decode('utf-8', errors='replace')
print(openp('/')[0])
print(openp('/login', {'next':'/orders','sso':'company'})[0])
q=urllib.parse.urlencode({'customer':'C001','from':'2026-08-01','to':'2026-10-31'})
url, body=openp('/orders?'+q)
print('filtered url', url)
print(body[body.find('<p id='):body.find('<table')])
print('export hrefs', re.findall(r'id=.export-csv. href=.([^"\']+)', body))
print('links', re.findall(r"href='(/orders/\d+)'", body))
# export
url2, csvbody=openp('/orders/export.csv?'+q)
print('export url', url2)
print('csv preview')
print(csvbody[:1000])
rows=list(csv.DictReader(io.StringIO(csvbody)))
print('rows count', len(rows), 'cust ids', sorted(set(r.get('CustomerID','') for r in rows)))
print('orders', [r['OrderID'] for r in rows])
if rows:
    url3, det=openp('/orders/'+rows[0]['OrderID'])
    print('detail url', url3)
    print(det[:5000])