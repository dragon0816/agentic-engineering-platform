from pathlib import Path
import csv, subprocess, json, sys
ws=Path.cwd()
for fn in ['orders_C001_2026-09.csv','invoices_C001_2026-09.csv']:
    p=ws/'output'/'downloads'/fn
    print('---', fn, p.exists())
    if p.exists():
        with open(p, newline='', encoding='utf-8-sig') as f:
            rows=list(csv.DictReader(f))
        print('headers', rows[0].keys() if rows else [])
        for r in rows: print(r)
print('--- quote cli list C001 Sep json ---')
cmd=[sys.executable, r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py','quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
p=subprocess.run(cmd, capture_output=True, text=True)
print('return', p.returncode)
print('stderr', p.stderr[:1000])
print('stdout', p.stdout[:4000])