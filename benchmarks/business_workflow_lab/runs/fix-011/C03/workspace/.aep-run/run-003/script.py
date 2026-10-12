from pathlib import Path
import subprocess, sys, json
CLI = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd'
projects=[f'P{i:03d}' for i in range(1,6)]
all_items=[]
for p in projects:
    cmd=[CLI,'quotes','list','--project',p,'--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']
    cp=subprocess.run(cmd, capture_output=True, text=True, shell=False)
    print('CMD', ' '.join(cmd), 'exit', cp.returncode)
    if cp.stderr.strip(): print('stderr:', cp.stderr.strip())
    print('stdout:', cp.stdout.strip()[:1000])
    if cp.returncode==0:
        data=json.loads(cp.stdout)
        all_items.extend(data.get('items',[]))
print('total header items', len(all_items), all_items)
if all_items:
    qid=all_items[0]['QuoteID']
    cmd=[CLI,'quotes','get',qid,'--format','json']
    cp=subprocess.run(cmd, capture_output=True, text=True, shell=False)
    print('\nGET sample', qid, 'exit', cp.returncode)
    if cp.stderr.strip(): print('stderr:', cp.stderr.strip())
    print(cp.stdout[:2000])