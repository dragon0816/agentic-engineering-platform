import urllib.request, urllib.error, time
for i in range(1,6):
    url=f'http://127.0.0.1:58649/t13/item/{i}'
    print('\nURL', url)
    for attempt in range(1,4):
        try:
            with urllib.request.urlopen(url, timeout=10) as r:
                txt=r.read(2000).decode('utf-8','replace')
                print('attempt', attempt, 'status', r.status, 'sample:', txt[:1000])
                break
        except urllib.error.HTTPError as e:
            body=e.read(500).decode('utf-8','replace')
            print('attempt', attempt, 'HTTPError', e.code, body[:200])
            if e.code != 500: break
            time.sleep(0.1)
        except Exception as e:
            print('attempt', attempt, type(e).__name__, e)
            break