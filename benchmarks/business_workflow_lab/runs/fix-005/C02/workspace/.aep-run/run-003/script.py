from pathlib import Path
import subprocess, json, sys
cli = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py'
cmd = [sys.executable, cli, 'quotes', 'list', '--from', '2026-09-01', '--to', '2026-09-30', '--format', 'json']
print('running:', cmd)
res = subprocess.run(cmd, capture_output=True, text=True)
print('returncode', res.returncode)
print('stderr', res.stderr[:1000])
print('stdout', res.stdout[:3000])
if res.returncode == 0:
    data=json.loads(res.stdout)
    print('count', data.get('count'))
    print('first items', data.get('items', [])[:3])
    if data.get('items'):
        qid=data['items'][0]['QuoteID']
        cmd2=[sys.executable, cli, 'quotes', 'get', qid, '--format', 'json']
        res2=subprocess.run(cmd2, capture_output=True, text=True)
        print('\nget first', qid, 'returncode', res2.returncode)
        print('stderr', res2.stderr[:1000])
        print('stdout', res2.stdout[:3000])