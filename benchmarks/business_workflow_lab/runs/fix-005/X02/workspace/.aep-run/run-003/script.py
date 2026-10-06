from pathlib import Path
import subprocess, json, csv, sys, os
ws=Path.cwd()
cmd=[sys.executable, r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py', 'quotes','list','--customer','C001','--from','2026-09-01','--to','2026-09-30','--format','json']
print('RUN', cmd)
p=subprocess.run(cmd, capture_output=True, text=True)
print('returncode', p.returncode)
print('stderr', p.stderr)
print('stdout', p.stdout[:4000])
if p.returncode!=0:
    raise SystemExit(p.returncode)
data=json.loads(p.stdout)
(out:=ws/'output').mkdir(exist_ok=True)
# save JSON and CSV for downstream
(out/'quotes_C001_2026-09.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
fields=['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount']
with open(out/'quotes_C001_2026-09.csv','w',newline='',encoding='utf-8-sig') as f:
    w=csv.DictWriter(f, fieldnames=fields)
    w.writeheader(); w.writerows(data.get('items',[]))
print('saved', out/'quotes_C001_2026-09.csv')