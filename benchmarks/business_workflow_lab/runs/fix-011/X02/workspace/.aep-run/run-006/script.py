import json, os
from pathlib import Path
params=json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))
ws=Path.cwd(); out=ws/'output'; dl=out/'downloads'
paths=[dl/'sap_orders_workflow.csv', dl/'sap_invoices_workflow.csv', out/f"expense_all_approved_{params['from_date']}_to_{params['to_date']}.csv"]
for p in paths:
    if p.exists():
        p.unlink()
        print('removed temp', p)
print('cleanup complete')
