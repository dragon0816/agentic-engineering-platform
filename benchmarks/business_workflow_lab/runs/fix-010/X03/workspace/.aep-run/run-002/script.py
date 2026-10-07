from pathlib import Path
from openpyxl import load_workbook

x03 = Path.cwd()
x01 = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\runs\fix-010\X01\workspace')
print('Current workspace:', x03)
print('Checking prior workflow workspace:', x01)
for p in sorted((x01/'output').rglob('*')):
    if p.is_file():
        print('X01 output:', p.relative_to(x01/'output'), p.stat().st_size, 'bytes')

src = x01/'output'/'project_integration_october_P003.xlsx'
print('Expected source exists:', src.exists(), src)
if src.exists():
    wb = load_workbook(src, data_only=False)
    print('Sheets:', wb.sheetnames)
    for s in ['Summary','Orders','Invoices','Expenses','Quotes','Exceptions','Report']:
        if s in wb.sheetnames:
            ws = wb[s]
            print('\nSheet', s, 'size', ws.max_row, 'x', ws.max_column)
            for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 10), values_only=True):
                print(row)
    # Count non-P003 ProjectID rows in data sheets. Headers in row 4 per template.
    for s in ['Summary','Orders','Invoices','Expenses','Quotes','Exceptions']:
        if s not in wb.sheetnames: continue
        ws=wb[s]
        headers=[ws.cell(4,c).value for c in range(1, ws.max_column+1)]
        if 'ProjectID' not in headers: continue
        pc=headers.index('ProjectID')+1
        vals=[]
        for r in range(5, ws.max_row+1):
            v=ws.cell(r,pc).value
            if v not in (None,''):
                vals.append(str(v))
        print('ProjectIDs in', s, ':', sorted(set(vals)), 'rows', len(vals))
