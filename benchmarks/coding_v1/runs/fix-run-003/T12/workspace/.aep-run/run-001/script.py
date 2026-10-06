from urllib.request import urlopen
urls=['http://127.0.0.1:51979/t12/a','http://127.0.0.1:51979/t12/b','http://127.0.0.1:51979/t12/c']
for u in urls:
    print('---',u)
    try:
        with urlopen(u, timeout=10) as r:
            data=r.read()
            print('status', getattr(r,'status',None), 'content-type', r.headers.get('Content-Type'), 'len', len(data))
            print(data[:1000].decode('utf-8','replace'))
    except Exception as e:
        print('ERROR',repr(e))
