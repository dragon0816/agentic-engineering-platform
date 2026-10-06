from pathlib import Path
import csv, subprocess, json, sys, os
base=Path('.')
print('Downloads/output files:')
for p in sorted((base/'output').rglob('*')):
    if p.is_file(): print('-', p, p.stat().st_size)
for rel in ['output/downloads/orders_C001_2026-09.csv','output/downloads/invoices_C001_2026-09.csv','output/expenses_2026-09_all_projects.csv']:
    p=base/rel
    print('\n---', rel, 'exists', p.exists(), '---')
    if p.exists():
        with open(p, newline='', encoding='utf-8-sig') as f:
            rdr=csv.reader(f)
            for i,row in zip(range(12), rdr): print(row)
cli=r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd'
cmd=[cli,'quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
print('\nRunning quote cli:', cmd)
res=subprocess.run(cmd, capture_output=True, text=True, shell=False)
print('return', res.returncode)
print('stdout', res.stdout[:5000])
print('stderr', res.stderr[:1000])
if res.returncode==0:
    out=base/'output'/'quotes_C001_2026-09.json'
    out.write_text(res.stdout, encoding='utf-8')
    print('wrote', out)