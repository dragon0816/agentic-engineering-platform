from pathlib import Path
import csv, subprocess, json, sys
ws=Path.cwd()
print('Downloads:')
for p in sorted((ws/'output'/'downloads').glob('*')):
    print('---', p.name, p.stat().st_size)
    try:
        with open(p, newline='', encoding='utf-8-sig') as f:
            r=list(csv.reader(f))
            print('rows incl header', len(r))
            for row in r[:5]: print(row)
    except Exception as e: print('read error', e)
cmd=[sys.executable, r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py','quotes','list','--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']
print('\nCLI:', cmd)
cp=subprocess.run(cmd, capture_output=True, text=True)
print('returncode', cp.returncode)
print('stderr', cp.stderr)
print('stdout', cp.stdout[:2000])
if cp.returncode==0:
    data=json.loads(cp.stdout)
    print('count', data.get('count'))
    for item in data.get('items',[])[:5]: print(item)
