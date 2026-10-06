from pathlib import Path
from urllib import request, parse
import http.cookiejar
base_url='http://127.0.0.1:8810/'
cj=http.cookiejar.CookieJar()
opener=request.build_opener(request.HTTPCookieProcessor(cj))
for url in [base_url, base_url+'sales-orders']:
    try:
        resp=opener.open(url, timeout=10)
        data=resp.read().decode('utf-8','replace')
        print('\nURL', url, 'status', resp.status, 'final', resp.geturl())
        print(data[:3000])
    except Exception as e:
        print('ERR', url, repr(e))