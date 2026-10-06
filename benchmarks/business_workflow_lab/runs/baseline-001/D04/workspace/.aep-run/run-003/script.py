from pathlib import Path
import json
p=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\operator\data\source.json')
print('exists', p.exists(), p)
if p.exists():
    data=json.loads(p.read_text(encoding='utf-8'))
    rows=[e for e in data['expenses'] if e['EmployeeID']=='E006' and '2026-01-01' <= e['ExpenseDate'] <= '2026-01-31']
    print('matching rows', len(rows))
    for r in rows:
        print(r)
    print('employees E006', [e for e in data['employees'] if e['EmployeeID']=='E006'])
    print('total expenses', len(data['expenses']))
