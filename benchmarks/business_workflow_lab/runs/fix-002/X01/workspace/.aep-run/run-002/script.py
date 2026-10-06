from pathlib import Path
import subprocess, sys, json, csv, os
from urllib.request import urlopen, Request
print('Inspect SAP home')
try:
    import requests
    r=requests.get('http://127.0.0.1:8810/', timeout=10)
    print('status', r.status_code, 'url', r.url, 'ct', r.headers.get('content-type'))
    print(r.text[:3000])
except Exception as e:
    print('SAP error', type(e).__name__, e)
print('\nInspect quote CLI help/list sample')
cli=r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd'
for args in ([cli,'--help'], [cli,'quotes','list','--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']):
    print('RUN', args)
    try:
        cp=subprocess.run(args, capture_output=True, text=True, timeout=30)
        print('return', cp.returncode)
        print('stdout', cp.stdout[:2000])
        print('stderr', cp.stderr[:1000])
    except Exception as e: print('ERR', type(e).__name__, e)
print('\nExpense export exists')
p=Path('output/expenses_2026-09_approved.csv')
print(p, p.exists(), p.stat().st_size if p.exists() else None)
if p.exists():
    with p.open(encoding='utf-8-sig', newline='') as f:
        rd=csv.reader(f)
        for i,row in zip(range(5),rd): print(row)
