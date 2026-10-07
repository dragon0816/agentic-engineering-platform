import subprocess, json, csv
from pathlib import Path
ws=Path.cwd()
cmd=['python', r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py','quotes','list','--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']
res=subprocess.run(cmd,capture_output=True,text=True)
print('return',res.returncode)
print('stderr',res.stderr[:1000])
print('stdout',res.stdout[:4000])
cmd2=['python', r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py','quotes','export','--from','2026-09-01','--to','2026-09-30','--status','Accepted','--output',str(ws/'output'/'downloads'/'quotes_2026-09_accepted.csv')]
res2=subprocess.run(cmd2,capture_output=True,text=True)
print('export return',res2.returncode)
print('export stderr',res2.stderr[:1000])
print('export stdout',res2.stdout[:1000])
p=ws/'output'/'downloads'/'quotes_2026-09_accepted.csv'
print('exists',p.exists(), p.stat().st_size if p.exists() else None)
if p.exists():
 with open(p, newline='', encoding='utf-8-sig') as f:
  r=csv.reader(f); 
  for i,row in zip(range(5),r): print(row)
