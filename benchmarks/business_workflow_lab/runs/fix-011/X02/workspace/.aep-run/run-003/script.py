import os, csv, json, subprocess, sys
from pathlib import Path
ws=Path.cwd()
print('downloads:')
for p in sorted((ws/'output'/'downloads').glob('*')):
    print(p, p.stat().st_size)
    try:
        with open(p, encoding='utf-8-sig', newline='') as f:
            rdr=csv.reader(f)
            for i,row in zip(range(10), rdr): print(' ', row)
    except Exception as e: print(' read err', e)
print('\noutput files:')
for p in sorted((ws/'output').glob('*')):
    if p.is_file():
        print(p.name, p.stat().st_size)
        try:
            with open(p, encoding='utf-8-sig', newline='') as f:
                for i,row in zip(range(10), csv.reader(f)): print(' ', row)
        except Exception as e: print(' read err',e)
print('\nquote cli customers C001/list?')
cmd=[sys.executable, r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py','quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
cp=subprocess.run(cmd,capture_output=True,text=True)
print('return', cp.returncode)
print('stdout', cp.stdout[:4000])
print('stderr', cp.stderr[:1000])
