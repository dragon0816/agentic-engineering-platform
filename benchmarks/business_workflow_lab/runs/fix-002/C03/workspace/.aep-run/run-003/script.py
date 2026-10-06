from pathlib import Path
import subprocess, sys, json
ws=Path.cwd()
cli=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')
projects=[f'P{i:03d}' for i in range(1,6)]
allq=[]
for project in projects:
    cmd=[sys.executable, str(cli), 'quotes','list','--project',project,'--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']
    res=subprocess.run(cmd,text=True,capture_output=True)
    print('\nPROJECT', project, 'rc', res.returncode)
    if res.stderr: print('stderr', res.stderr)
    data=json.loads(res.stdout)
    print('count', data['count'])
    for item in data['items']:
        print(item)
        allq.append(item['QuoteID'])
print('\nGET sample/all')
for qid in allq:
    res=subprocess.run([sys.executable,str(cli),'quotes','get',qid,'--format','json'], text=True, capture_output=True)
    print('qid',qid,'rc',res.returncode)
    data=json.loads(res.stdout)
    print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])