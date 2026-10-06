from pathlib import Path
import csv
from openpyxl import load_workbook
base=Path('.')
rows=[]
with open(base/'output'/'expense_export.csv', newline='', encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
rows.sort(key=lambda r:(r['ExpenseDate'], r['ExpenseID']))
wb=load_workbook(base/'output'/'expense_report.xlsx')
ws=wb['Details']
for i,src in enumerate(rows,start=5):
    exp=src['ReceiptID']; got=ws.cell(i,11).value
    if exp!=got:
        print('mismatch row',i,'id',src['ExpenseID'], 'expected',repr(exp),'got',repr(got))
        print('row values', [ws.cell(i,c).value for c in range(1,15)])
        print('src', src)
        break
print('first 20 xlsx ids:', [(r,ws.cell(r,1).value,ws.cell(r,5).value,ws.cell(r,11).value) for r in range(5,ws.max_row+1)])
print('source sorted:', [(r['ExpenseID'], r['ExpenseDate'], r['ReceiptID']) for r in rows])