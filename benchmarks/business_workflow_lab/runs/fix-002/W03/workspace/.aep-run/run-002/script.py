from pathlib import Path
import urllib.request, urllib.parse
print('sap_manual.md full:')
print((Path('input')/'sap_manual.md').read_text(encoding='utf-8'))
url='http://127.0.0.1:8810/'
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        data=r.read(4000)
        print('URL status', r.status, r.geturl(), r.headers.get('content-type'))
        print(data.decode('utf-8', errors='replace'))
except Exception as e:
    print('URL error', type(e).__name__, e)
