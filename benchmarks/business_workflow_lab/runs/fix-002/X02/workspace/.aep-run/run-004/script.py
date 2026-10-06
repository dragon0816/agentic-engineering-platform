from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode
import http.cookiejar, traceback
base='http://127.0.0.1:8810/'
cj=http.cookiejar.CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))
for path in ['', 'sales-orders', 'invoices', 'login']:
    url=base+path
    try:
        r=opener.open(Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=5)
        data=r.read().decode('utf-8','replace')
        print('\nURL', url, 'status', r.status, 'final', r.geturl())
        print(data[:2000])
    except Exception:
        print('ERR', url); traceback.print_exc()
