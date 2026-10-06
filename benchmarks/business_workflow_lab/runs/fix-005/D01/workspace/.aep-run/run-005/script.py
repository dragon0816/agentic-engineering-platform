import os, json, re
from pathlib import Path
params=json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))
workspace=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\runs\fix-005\D01\workspace')
out=workspace/'output'
out.mkdir(exist_ok=True)
emp=params['employee_id']
df=params['date_from']
dt=params['date_to']
export_name=f'expense_export_{emp}_{df}_{dt}.xlsx'
for name in [export_name, params.get('output_file','')]:
    if name:
        p=out/name
        if p.exists():
            p.unlink()
            print('removed', p)
        else:
            print('not present', p)
print('cleanup complete')