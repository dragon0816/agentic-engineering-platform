import urllib.request, urllib.error
for i in range(1,6):
    url=f'http://127.0.0.1:50351/t13/item/{i}'
    print('\n---', url, '---')
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            print('status', r.status)
            print(r.read().decode('utf-8', errors='replace')[:2000])
    except urllib.error.HTTPError as e:
        print('HTTPError', e.code)
        try:
            print(e.read().decode('utf-8', errors='replace')[:500])
        except Exception as ex:
            print('read err', ex)
    except Exception as e:
        print(type(e).__name__, e)