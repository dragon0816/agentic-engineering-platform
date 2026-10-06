from pathlib import Path
import json
from decimal import Decimal, ROUND_HALF_UP
p=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\operator\data\source.json')
data=json.loads(p.read_text(encoding='utf-8'))
recs=[e for e in data['expenses'] if '2026-09-01'<=e['ExpenseDate']<='2026-09-30' and e['Status'] in ('Submitted','Approved')]
print('count', len(recs))
for e in sorted(recs, key=lambda x:(x['ExpenseDate'], x['ExpenseID'])):
    print(e)
print('missing', [e['ExpenseID'] for e in recs if e['MissingReceipt']])
