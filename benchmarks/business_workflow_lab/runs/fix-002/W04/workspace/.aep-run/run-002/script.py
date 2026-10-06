from pathlib import Path
import requests
base='http://127.0.0.1:8810/'
s=requests.Session()
for url in [base]:
    r=s.get(url, timeout=10)
    print('GET', url, 'status', r.status_code, 'url', r.url)
    print('headers content-type', r.headers.get('content-type'))
    print(r.text[:2000])
    print('cookies', s.cookies.get_dict())
