from pathlib import Path
import requests
base='http://127.0.0.1:8810/'
s=requests.Session()
for url in [base, base+'sales-orders', base+'invoices']:
    try:
        r=s.get(url, timeout=5)
        print('\nURL', url, 'status', r.status_code, 'final', r.url)
        print(r.text[:1500])
    except Exception as e:
        print('ERR', url, repr(e))