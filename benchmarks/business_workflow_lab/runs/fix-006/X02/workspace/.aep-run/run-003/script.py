from pathlib import Path
import csv, subprocess, json, sys
ws=Path.cwd()
print('Downloaded ERP files:')
for p in sorted((ws/'output'/'downloads').glob('*.csv')):
    print('\n--', p.name)
    with open(p, newline='', encoding='utf-8-sig') as f:
        r=csv.reader(f)
        for i,row in zip(range(10), r): print(i,row)
cli = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd'
cmd=[cli,'quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
print('\nRunning quote CLI:', cmd)
res=subprocess.run(cmd, capture_output=True, text=True, shell=False)
print('returncode', res.returncode)
print('stderr', res.stderr[:1000])
print('stdout', res.stdout[:3000])
if res.returncode==0:
    data=json.loads(res.stdout)
    out=ws/'output'/'downloads'/'quotes_C001_2026-09.json'
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print('saved', out)
    print('project IDs from ERP+quotes:')
    projects=set()
    for p in [(ws/'output'/'downloads'/'orders_C001_2026-09.csv'),(ws/'output'/'downloads'/'invoices_C001_2026-09.csv')]:
        with open(p, newline='', encoding='utf-8-sig') as f:
            for row in csv.DictReader(f):
                if row.get('ProjectID'): projects.add(row['ProjectID'])
    for item in data.get('items',[]):
        if item.get('ProjectID'): projects.add(item['ProjectID'])
    print(sorted(projects))