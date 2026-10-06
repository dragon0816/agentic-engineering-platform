from pathlib import Path
import requests
s=requests.Session()
base='http://127.0.0.1:8810'
try:
    r=s.get(base+'/login', timeout=5)
    print('login status', r.status_code, r.url)
    print(r.text[:2000])
    r=s.post(base+'/login', data={'username':'lab.analyst','password':'Lab#2026'}, timeout=5, allow_redirects=True)
    print('post status', r.status_code, r.url)
    print(r.text[:2000])
    for path in ['/invoices','/invoices?date_from=2026-09-01&date_to=2026-09-30','/invoices/export?date_from=2026-09-01&date_to=2026-09-30']:
        rr=s.get(base+path, timeout=5)
        print('\nPATH', path, rr.status_code, rr.url, rr.headers.get('content-type'))
        print(rr.text[:1000])
except Exception as e:
    print('ERR', type(e), e)
