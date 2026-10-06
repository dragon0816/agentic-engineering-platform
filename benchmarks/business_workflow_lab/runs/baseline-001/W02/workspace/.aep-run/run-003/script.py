from pathlib import Path
import urllib.request, urllib.parse, http.cookiejar, re
from html.parser import HTMLParser
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar(); opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
def req(method,path,data=None):
    if data is not None:
        data=urllib.parse.urlencode(data).encode()
        request=urllib.request.Request(base+path,data=data,method=method)
    else:
        request=urllib.request.Request(base+path,method=method)
    with opener.open(request,timeout=10) as r:
        return r.geturl(), r.read().decode('utf-8',errors='replace')
req('GET','/login')
url,html=req('POST','/login', {'username':'lab.analyst','password':'Lab#2026'})
params={'customer':'C001','from':'2026-08-01','to':'2026-10-31','sort':'OrderDate','order':'asc'}
path='/orders?'+urllib.parse.urlencode(params)
url,html=req('GET',path)
print('URL',url,'len',len(html))
Path('output/workflow/filtered_orders.html').write_text(html,encoding='utf-8')
print(html[html.find('<form'):html.find('</form>')+7])
print('TOTAL match', re.findall(r'Total:[^<]+', html))
print('links')
for m in re.finditer(r"href='([^']+)'|href=\"([^\"]+)\"", html):
    href=m.group(1) or m.group(2)
    print(href)
print('table segment')
start=html.find('<table'); end=html.find('</table>')+8
print(html[start:end])