import subprocess, json, os, csv
from pathlib import Path
cli = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd'
cmd=[cli,'quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
print('RUN', cmd)
p=subprocess.run(cmd,capture_output=True,text=True)
print('returncode',p.returncode)
print('stdout',p.stdout)
print('stderr',p.stderr)
if p.returncode==0:
    out=Path('output/downloads/quotes_C001_2026-09.json')
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(p.stdout,encoding='utf-8')
    data=json.loads(p.stdout)
    print('count', data.get('count'), 'projects', sorted({i.get('ProjectID','') for i in data.get('items',[])}))
