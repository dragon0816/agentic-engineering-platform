from urllib.request import urlopen, Request
from urllib.parse import urlencode
import re
url='http://127.0.0.1:8810/'
try:
    with urlopen(url, timeout=10) as resp:
        data=resp.read().decode('utf-8','replace')
        print('status', resp.status, 'url', resp.geturl(), 'ct', resp.headers.get('content-type'))
        print(data[:5000])
except Exception as e:
    print('ERR', type(e).__name__, e)
