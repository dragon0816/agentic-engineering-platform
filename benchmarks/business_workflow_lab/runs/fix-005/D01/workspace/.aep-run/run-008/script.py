import json, os
from pathlib import Path
params=json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))
ws=Path.cwd()
out=ws/'output'
out.mkdir(exist_ok=True)
export=out/f"expense_export_{params['employee_id']}_{params['date_from']}_{params['date_to']}.xlsx"
final=out/params['output_file']
for p in [export, final]:
    if p.exists():
        p.unlink()
        print('removed', p)
print('cleanup complete')