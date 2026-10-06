from pathlib import Path
base=Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab')
for rel in ['expense_desktop_mock/expense_app.py','operator/data/source.json','expense_desktop_mock/ExpenseApp.cs']:
    p=base/rel
    print('\n###', rel, p.stat().st_size)
    txt=p.read_text(encoding='utf-8', errors='replace')
    # print lines with export/data load
    for i,line in enumerate(txt.splitlines(),1):
        if any(k in line.lower() for k in ['expense','source.json','export','csv','approved','projectid']):
            print(f'{i}: {line[:220]}')
            if i>250 and rel.endswith('.py'): pass
    print('--- head ---')
    print(txt[:1500])
