from pathlib import Path
from urllib.request import urlopen
urls = ['http://127.0.0.1:49257/t12/a','http://127.0.0.1:49257/t12/b','http://127.0.0.1:49257/t12/c']
for url in urls:
    print('---', url)
    with urlopen(url, timeout=10) as r:
        data = r.read()
        print('status', getattr(r,'status',None), 'content-type', r.headers.get('content-type'), 'bytes', len(data))
        print(data[:1000].decode('utf-8', errors='replace'))
