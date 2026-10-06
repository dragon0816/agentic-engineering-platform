from pathlib import Path
import subprocess, json, sys, os
ws=Path.cwd()
cli=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')
projects=[f'P{i:03d}' for i in range(1,6)]
print('cli exists', cli.exists(), cli)
for p in projects:
    cmd=[sys.executable, str(cli), 'quotes','list','--project',p,'--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']
    cp=subprocess.run(cmd, capture_output=True, text=True)
    print('\nPROJECT', p, 'return', cp.returncode)
    if cp.stderr.strip(): print('stderr:', cp.stderr.strip())
    print(cp.stdout[:1000])
    if cp.returncode==0:
        data=json.loads(cp.stdout)
        for item in data.get('items',[]):
            qid=item['QuoteID']
            get=[sys.executable, str(cli), 'quotes','get',qid,'--format','json']
            gp=subprocess.run(get, capture_output=True, text=True)
            print('GET', qid, 'return', gp.returncode, gp.stdout[:500], 'stderr', gp.stderr.strip())
