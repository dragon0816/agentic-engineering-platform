from pathlib import Path
import csv, subprocess, json, sys
ws=Path.cwd()
print('Downloads:')
for p in (ws/'output'/'downloads').glob('*'):
    print('-', p.name, p.stat().st_size)
    with p.open(newline='', encoding='utf-8-sig') as f:
        rows=list(csv.reader(f))
    print(' rows incl header', len(rows))
    for r in rows[:10]: print(' ', r)

cli=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd')
cmd=[str(cli),'quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
print('RUN', cmd)
res=subprocess.run(cmd, capture_output=True, text=True, shell=False)
print('returncode', res.returncode)
print('stderr', res.stderr[:1000])
print('stdout', res.stdout[:3000])
if res.returncode==0:
    data=json.loads(res.stdout)
    print('quote count', data.get('count'))
    projects=sorted({it.get('ProjectID') for it in data.get('items',[])})
    print('quote projects', projects)
    for it in data.get('items',[]): print(it)