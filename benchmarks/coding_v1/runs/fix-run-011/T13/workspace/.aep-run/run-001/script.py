from urllib.request import urlopen, Request
from urllib.error import HTTPError, URLError
url='http://127.0.0.1:54763/t13/list'
print('workspace inputs: URL=', url)
try:
    req=Request(url, headers={'User-Agent':'Mozilla/5.0'})
    with urlopen(req, timeout=10) as r:
        print('status:', r.status)
        print('content-type:', r.headers.get('content-type'))
        data=r.read(5000).decode('utf-8', errors='replace')
        print('first 5000 chars:')
        print(data)
except HTTPError as e:
    print('HTTPError', e.code)
    print(e.read(1000).decode('utf-8', errors='replace'))
except URLError as e:
    print('URLError', e)
