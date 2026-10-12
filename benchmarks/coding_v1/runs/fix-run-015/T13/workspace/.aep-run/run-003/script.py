import urllib.request, urllib.error
for i in range(1,6):
    url=f'http://127.0.0.1:50447/t13/item/{i}'
    print('\nURL', url)
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data=r.read().decode('utf-8', errors='replace')
            print('status', r.status, 'bytes', len(data))
            print(data[:2000])
    except urllib.error.HTTPError as e:
        print('HTTPError', e.code)
    except Exception as e:
        print(type(e).__name__, e)