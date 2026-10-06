from pathlib import Path
import subprocess, sys, json, os, csv, requests, re, textwrap, time
root=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab')
print('root exists', root.exists())
for sub in ['quote_cli_mock','expense_desktop_mock']:
    p=root/sub
    print('\n',p, p.exists())
    if p.exists():
        for q in sorted(p.rglob('*')):
            print(q.relative_to(p), 'DIR' if q.is_dir() else f'FILE {q.stat().st_size}')

# try quote CLI
cmd=[sys.executable, str(root/'quote_cli_mock'/'run_quote_cli.py'), 'quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
print('\nRunning quote list:', cmd)
r=subprocess.run(cmd, capture_output=True, text=True)
print('rc', r.returncode, 'stdout', r.stdout[:2000], 'stderr', r.stderr[:1000])

# try requests web
try:
    s=requests.Session()
    r=s.get('http://127.0.0.1:8810/login', timeout=5)
    print('\nlogin get', r.status_code, r.url, r.text[:300])
    r=s.post('http://127.0.0.1:8810/login', data={'username':'lab.analyst','password':'Lab#2026'}, timeout=5, allow_redirects=True)
    print('login post', r.status_code, r.url, r.text[:500])
    # try likely paths
    for path in ['/sales_orders','/orders','/invoices','/sales-orders']:
        rr=s.get('http://127.0.0.1:8810'+path, timeout=5)
        print(path, rr.status_code, rr.url, rr.text[:120])
except Exception as e:
    print('web error', type(e), e)
