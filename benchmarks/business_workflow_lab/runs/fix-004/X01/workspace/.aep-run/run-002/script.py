import csv, subprocess, json, os
from pathlib import Path
ws=Path.cwd()
for rel in ['output/downloads/sap_orders_2026_09.csv','output/downloads/sap_invoices_2026_09.csv','output/expense_approved_2026_09.csv']:
    p=ws/rel
    print('\n---',rel,p.exists(),p.stat().st_size if p.exists() else None)
    if p.exists():
        with open(p, newline='', encoding='utf-8-sig') as f:
            r=csv.reader(f)
            for i,row in zip(range(8), r): print(row)
cmd=['python', r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py','quotes','list','--from','2026-09-01','--to','2026-09-30','--status','Accepted','--format','json']
print('\nRUN',' '.join(cmd))
res=subprocess.run(cmd, capture_output=True, text=True)
print('return',res.returncode)
print('stdout',res.stdout[:2000])
print('stderr',res.stderr[:2000])