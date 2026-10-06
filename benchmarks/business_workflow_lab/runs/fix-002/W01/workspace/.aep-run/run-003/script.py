from urllib import request, parse
import http.cookiejar, re
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar(); op=request.build_opener(request.HTTPCookieProcessor(cj))
# login
html=op.open(base+'/login?next=/orders').read().decode('utf-8','replace')
post=parse.urlencode({'next':'/orders','sso':'company'}).encode()
resp=op.open(request.Request(base+'/login', data=post, method='POST'), timeout=10)
html=resp.read().decode('utf-8','replace')
print('login final', resp.geturl(), 'status', resp.status)
print(html[:1000])
# sales orders page
url=base+'/orders?date_from=2026-09-01&date_to=2026-09-30&status=Open&sort_by=OrderID&order=asc'
resp=op.open(url, timeout=10)
html=resp.read().decode('utf-8','replace')
print('\norders final', resp.geturl(), 'status', resp.status, 'len', len(html))
print(html[:5000])
print('\nlinks:', re.findall(r'href=["\']([^"\']+)', html)[:30])
print('\nforms actions:', re.findall(r'<form[^>]+>', html)[:5])