from pathlib import Path
from openpyxl import load_workbook
from decimal import Decimal, ROUND_HALF_UP
from collections import defaultdict
out=Path.cwd()/'output'/'E001_september_expenses.xlsx'
print('checking', out, out.exists(), out.stat().st_size if out.exists() else None)
wb=load_workbook(out, data_only=False)
print('sheets', wb.sheetnames)
expected_sheets=['Report','Details','Summary','Exceptions','Instructions']
assert wb.sheetnames==expected_sheets, wb.sheetnames
# headers
for sheet, headers in {
    'Details':['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','AmountTWD','Status','ReceiptID','Description','MissingReceipt','NeedsReview'],
    'Summary':['Group','SubGroup','Currency','Amount','AmountTWD','Count'],
    'Exceptions':['ExpenseID','EmployeeID','ExpenseDate','Reason']
}.items():
    ws=wb[sheet]
    got=[ws.cell(4,c).value for c in range(1,len(headers)+1)]
    print(sheet,'headers',got)
    assert got==headers
# detail rows
ws=wb['Details']
rows=[]
r=5
while ws.cell(r,1).value:
    rows.append([ws.cell(r,c).value for c in range(1,15)])
    r+=1
print('detail row count', len(rows))
assert len(rows)==13
assert {row[1] for row in rows}=={'E001'}
assert min(row[4] for row in rows)=='2026-09-01'
assert max(row[4] for row in rows)=='2026-09-30'
for row in rows:
    assert isinstance(row[0], str) and isinstance(row[1], str) and isinstance(row[3], str)
    assert isinstance(row[7], (int,float)) and isinstance(row[8], (int,float))
    assert row[12] in ('true','false') and row[13] in ('true','false')
# manual totals and summary groups
manual=Decimal('0')
groups=defaultdict(lambda:[Decimal('0'),Decimal('0'),0])
for row in rows:
    status=row[9]; cur=row[6]; amt=Decimal(str(row[7])); twd=Decimal(str(row[8]))
    manual += twd
    groups[(status,cur)][0]+=amt; groups[(status,cur)][1]+=twd; groups[(status,cur)][2]+=1
print('manual TWD total', manual)
assert wb['Summary']['B2'].value=='=SUM(Details!I5:I17)'
ws=wb['Summary']
sum_rows=[]
r=5
while ws.cell(r,1).value:
    sum_rows.append([ws.cell(r,c).value for c in range(1,7)])
    r+=1
print('summary rows', sum_rows)
# validate all status/currency groups before TOTAL_TWD row
for row in sum_rows:
    if row[0]=='TOTAL_TWD':
        assert row[2]=='TWD' and row[5]==13
        continue
    key=(row[0], row[2])
    assert key in groups, key
    assert Decimal(str(row[3])).quantize(Decimal('0.01'))==groups[key][0].quantize(Decimal('0.01'))
    assert Decimal(str(row[4])).quantize(Decimal('0.01'))==groups[key][1].quantize(Decimal('0.01'))
    assert row[5]==groups[key][2]
print('summary group count including total row', len(sum_rows))
# exceptions
ws=wb['Exceptions']
exc=[]; r=5
while ws.cell(r,1).value:
    exc.append([ws.cell(r,c).value for c in range(1,5)])
    r+=1
print('exceptions', exc)
assert len(exc)==sum(1 for row in rows if row[12]=='true')
print('CHECK PASSED: workbook sheets, headers, 13 detail rows, employee/date filters, numeric amounts, text IDs, true/false flags, Summary groups, Summary!B2 formula, Exceptions list.')