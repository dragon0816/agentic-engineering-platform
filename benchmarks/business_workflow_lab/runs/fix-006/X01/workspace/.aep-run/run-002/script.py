from pathlib import Path
import csv, subprocess, json, sys
ws = Path.cwd()
print('OUTPUT TREE')
for p in sorted((ws/'output').rglob('*')):
    if p.is_file():
        print('-', p.relative_to(ws), p.stat().st_size)
        if p.suffix.lower()=='.csv':
            with p.open(newline='', encoding='utf-8-sig') as f:
                r=csv.reader(f)
                for i,row in zip(range(4), r): print(' ', i, row)

cmd = [sys.executable, r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py', 'quotes','list','--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']
print('\nRUN CLI:', cmd)
res=subprocess.run(cmd, capture_output=True, text=True)
print('returncode', res.returncode)
print('stderr', res.stderr[:1000])
print('stdout', res.stdout[:3000])
if res.returncode==0:
    data=json.loads(res.stdout)
    print('count', data.get('count'))
    if data.get('items'):
        print('first item keys', list(data['items'][0].keys()))
        print('first item', data['items'][0])
