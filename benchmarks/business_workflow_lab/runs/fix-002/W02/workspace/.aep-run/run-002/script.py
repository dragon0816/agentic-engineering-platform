from pathlib import Path
import urllib.request
url='http://127.0.0.1:8810/'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data=r.read(5000)
        print('status', r.status, 'url', r.geturl())
        print('headers', dict(r.headers))
        print(data.decode('utf-8', errors='replace'))
except Exception as e:
    print('ERROR', type(e).__name__, e)