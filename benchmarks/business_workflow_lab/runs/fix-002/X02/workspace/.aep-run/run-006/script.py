from pathlib import Path
from urllib.request import Request, build_opener, HTTPCookieProcessor
from urllib.parse import urlencode
import http.cookiejar, csv, subprocess, json, sys, os
ws=Path.cwd(); out=ws/'output'; out.mkdir(exist_ok=True)
base='http://127.0.0.1:8810'
cj=http.cookiejar.CookieJar(); opener=build_opener(HTTPCookieProcessor(cj))
# login
opener.open(Request(base+'/', headers={'User-Agent':'Mozilla/5.0'}), timeout=5).read()
body=urlencode({'next':'/orders','sso':'company'}).encode()
opener.open(Request(base+'/login', data=body, headers={'User-Agent':'Mozilla/5.0','Content-Type':'application/x-www-form-urlencoded'}), timeout=5).read()
for endpoint,name in [('/orders/export.csv','orders'),('/invoices/export.csv','invoices')]:
    qs=urlencode({'customer':'C001','from':'2026-09-01','to':'2026-09-30'})
    url=base+endpoint+'?'+qs
    r=opener.open(Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=10)
    data=r.read()
    p=out/f'{name}_C001_2026-09.csv'
    p.write_bytes(data)
    print('\nDownloaded', name, r.status, r.geturl(), 'bytes', len(data), 'to', p)
    txt=data.decode('utf-8-sig','replace')
    print(txt[:2000])

cli=r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd'
cmd=[cli,'quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
print('\nRunning', cmd)
cp=subprocess.run(cmd, capture_output=True, text=True, shell=False)
print('rc', cp.returncode, 'stderr', cp.stderr[:500])
print(cp.stdout[:3000])
(out/'quotes_C001_2026-09.json').write_text(cp.stdout, encoding='utf-8')
