from urllib.request import urlopen
for url in ['http://127.0.0.1:50447/t11/item/1','http://127.0.0.1:50447/t11/item/3']:
    print('\nURL:', url)
    with urlopen(url, timeout=10) as resp:
        text = resp.read().decode(resp.headers.get_content_charset() or 'utf-8', errors='replace')
    print(text[:4000])
