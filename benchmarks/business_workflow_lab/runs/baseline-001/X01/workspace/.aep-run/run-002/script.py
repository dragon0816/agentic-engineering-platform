from pathlib import Path
import subprocess, sys, os, json, textwrap
# Check mock directories and availability
root=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab')
print('root exists', root.exists())
for name in ['quote_cli_mock','expense_desktop_mock']:
    d=root/name
    print('\nDIR', d, d.exists())
    if d.exists():
        for p in sorted(d.iterdir()): print(' ', p.name, p.stat().st_size if p.is_file() else 'dir')
# run quote CLI
cmd=[sys.executable, str(root/'quote_cli_mock'/'run_quote_cli.py'), 'quotes', 'list', '--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']
print('\nrun quote:', cmd)
r=subprocess.run(cmd, capture_output=True, text=True, timeout=30)
print('rc', r.returncode)
print('stdout', r.stdout[:2000])
print('stderr', r.stderr[:1000])
# test SAP HTTP
try:
    import requests
    s=requests.Session()
    resp=s.get('http://127.0.0.1:8810/login', timeout=5)
    print('\nSAP login get', resp.status_code, resp.url, resp.text[:300])
    resp=s.post('http://127.0.0.1:8810/login', data={'username':'lab.analyst','password':'Lab#2026'}, timeout=5, allow_redirects=True)
    print('SAP login post', resp.status_code, resp.url, resp.text[:500])
except Exception as e:
    print('SAP error', type(e).__name__, e)
