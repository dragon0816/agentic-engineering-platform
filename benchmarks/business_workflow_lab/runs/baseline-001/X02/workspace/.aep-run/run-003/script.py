from pathlib import Path
import subprocess, sys, json, os, csv, re, textwrap, time
from urllib import request, parse
from http.cookiejar import CookieJar
root=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab')
print('root exists', root.exists())
for sub in ['quote_cli_mock','expense_desktop_mock']:
    p=root/sub
    print('\n',p, p.exists())
    if p.exists():
        for q in sorted(p.rglob('*')):
            print(q.relative_to(p), 'DIR' if q.is_dir() else f'FILE {q.stat().st_size}')

cmd=[sys.executable, str(root/'quote_cli_mock'/'run_quote_cli.py'), 'quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
print('\nRunning quote list:', cmd)
r=subprocess.run(cmd, capture_output=True, text=True)
print('rc', r.returncode, 'stdout', r.stdout[:4000], 'stderr', r.stderr[:1000])

# urllib session
try:
    cj=CookieJar(); opener=request.build_opener(request.HTTPCookieProcessor(cj))
    resp=opener.open('http://127.0.0.1:8810/login', timeout=5)
    txt=resp.read().decode('utf-8', errors='replace')
    print('\nlogin get', resp.status, resp.geturl(), txt[:300])
    data=parse.urlencode({'username':'lab.analyst','password':'Lab#2026'}).encode()
    resp=opener.open(request.Request('http://127.0.0.1:8810/login', data=data), timeout=5)
    txt=resp.read().decode('utf-8', errors='replace')
    print('login post', resp.status, resp.geturl(), txt[:1000])
    for path in ['/sales_orders','/orders','/invoices','/sales-orders','/customers']:
        try:
            rr=opener.open('http://127.0.0.1:8810'+path, timeout=5)
            t=rr.read().decode('utf-8', errors='replace')
            print('\nPATH', path, rr.status, rr.geturl(), t[:500])
        except Exception as e:
            print('path error', path, type(e), e)
except Exception as e:
    print('web error', type(e), e)
