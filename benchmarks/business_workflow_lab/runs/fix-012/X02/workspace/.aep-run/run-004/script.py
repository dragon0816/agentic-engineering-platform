import csv, json, subprocess, sys
from pathlib import Path
from decimal import Decimal
ws=Path.cwd(); dl=ws/'output'/'downloads'
print('downloads:', sorted(p.name for p in dl.glob('*')))
for name in ['sap_orders_C001_2026-09.csv','sap_invoices_C001_2026-09.csv']:
    print('\n---', name, '---')
    with open(dl/name, encoding='utf-8-sig', newline='') as f:
        rows=list(csv.DictReader(f))
    print('count', len(rows), 'headers', rows[0].keys() if rows else [])
    for r in rows: print(r)
cmd=[sys.executable, r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py','quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
print('\nCMD', cmd)
p=subprocess.run(cmd, text=True, capture_output=True)
print('returncode', p.returncode)
print('stderr', p.stderr)
print('stdout', p.stdout)
