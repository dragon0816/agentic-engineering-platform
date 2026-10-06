from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
import csv, json

ws=Path.cwd(); inp=ws/'input'; out=ws/'output'; out.mkdir(exist_ok=True)
print('Inputs inspected for final run:')
for p in sorted(inp.iterdir()): print('-', p.name, p.stat().st_size)
print('Raw extracted files:')
for p in sorted(out.glob('*2026-09*')): print('-', p.name, p.stat().st_size)

START='2026-09-01'; END='2026-09-30'; CUSTOMER='C001'; TODAY=date(2026,10,6)
Q=Decimal('0.01')
def money(x): return Decimal(str(x)).quantize(Q, rounding=ROUND_HALF_UP)
def twd(amount,currency,rates): return money(Decimal(str(amount))*rates[currency])
def read_csv_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as f: return list(csv.DictReader(f))

rates={}
with open(inp/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    r=csv.reader(f); next(r)
    for row in r:
        if row: rates[row[0]]=Decimal(row[1])
orders=read_csv_rows(out/'orders_C001_2026-09.csv')
invoices=read_csv_rows(out/'invoices_C001_2026-09.csv')
quotes=json.loads((out/'quotes_C001_2026-09.json').read_text(encoding='utf-8'))['items']
projects=sorted({r['ProjectID'] for r in orders} | {r['ProjectID'] for r in invoices} | {r['ProjectID'] for r in quotes})
expenses=[]
for proj in projects:
    p=out/f'expenses_{proj}_2026-09.csv'
    if p.exists(): expenses.extend(read_csv_rows(p))
print('Counts loaded:', {'orders':len(orders),'invoices':len(invoices),'expenses':len(expenses),'quotes':len(quotes),'projects':projects})

wb=load_workbook(inp/'project_template.xlsx')
for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    sh=wb[s]
    if sh.max_row>=5: sh.delete_rows(5, sh.max_row-4)

def set_text(cell, value):
    cell.value='' if value is None else str(value); cell.number_format='@'
def set_date_text(cell, value):
    cell.value=str(value); cell.number_format='yyyy-mm-dd'
def set_amount(cell, value):
    cell.value=float(money(value)); cell.number_format='0.00'

sh=wb['Orders']
for i,r in enumerate(orders, 5):
    set_text(sh.cell(i,1), r['OrderID']); set_text(sh.cell(i,2), r['ProjectID']); set_text(sh.cell(i,3), r['CustomerID'])
    set_date_text(sh.cell(i,4), r['OrderDate']); set_text(sh.cell(i,5), r['Status']); set_text(sh.cell(i,6), r['Currency'])
    set_amount(sh.cell(i,7), r['NetAmount']); set_amount(sh.cell(i,8), twd(r['NetAmount'], r['Currency'], rates))
sh=wb['Invoices']
for i,r in enumerate(invoices, 5):
    set_text(sh.cell(i,1), r['InvoiceID']); set_text(sh.cell(i,2), r['OrderID']); set_text(sh.cell(i,3), r['ProjectID']); set_text(sh.cell(i,4), r['CustomerID'])
    set_date_text(sh.cell(i,5), r['InvoiceDate']); set_date_text(sh.cell(i,6), r['DueDate']); set_text(sh.cell(i,7), r['Currency'])
    set_amount(sh.cell(i,8), r['Amount']); set_amount(sh.cell(i,9), r['PaidAmount'])
    bal=money(Decimal(r['Amount'])-Decimal(r['PaidAmount']))
    set_amount(sh.cell(i,10), bal); set_amount(sh.cell(i,11), twd(bal, r['Currency'], rates))
expenses.sort(key=lambda r:(r['ProjectID'], r['ExpenseDate'], r['ExpenseID']))
sh=wb['Expenses']
for i,r in enumerate(expenses, 5):
    set_text(sh.cell(i,1), r['ExpenseID']); set_text(sh.cell(i,2), r['ProjectID']); set_text(sh.cell(i,3), r['EmployeeID'])
    set_date_text(sh.cell(i,4), r['ExpenseDate']); set_text(sh.cell(i,5), r['Status']); set_text(sh.cell(i,6), r['Currency'])
    set_amount(sh.cell(i,7), r['Amount']); set_amount(sh.cell(i,8), twd(r['Amount'], r['Currency'], rates))
sh=wb['Quotes']
for i,r in enumerate(quotes, 5):
    set_text(sh.cell(i,1), r['QuoteID']); set_text(sh.cell(i,2), r['ProjectID']); set_text(sh.cell(i,3), r['CustomerID'])
    set_date_text(sh.cell(i,4), r['QuoteDate']); set_date_text(sh.cell(i,5), r['ValidUntil']); set_text(sh.cell(i,6), r['Status']); set_text(sh.cell(i,7), r['Currency'])
    set_amount(sh.cell(i,8), r['NetAmount']); set_amount(sh.cell(i,9), twd(r['NetAmount'], r['Currency'], rates))

summary={p:{'OrderTWD':Decimal('0'),'InvoiceBalanceTWD':Decimal('0'),'ApprovedExpenseTWD':Decimal('0'),'AcceptedQuoteTWD':Decimal('0')} for p in projects}
for r in orders:
    if r['Status']!='Cancelled': summary[r['ProjectID']]['OrderTWD']+=twd(r['NetAmount'], r['Currency'], rates)
for r in invoices:
    bal=money(Decimal(r['Amount'])-Decimal(r['PaidAmount']))
    summary[r['ProjectID']]['InvoiceBalanceTWD']+=twd(bal, r['Currency'], rates)
for r in expenses:
    if r['Status']=='Approved': summary[r['ProjectID']]['ApprovedExpenseTWD']+=twd(r['Amount'], r['Currency'], rates)
for r in quotes:
    if r['Status']=='Accepted': summary[r['ProjectID']]['AcceptedQuoteTWD']+=twd(r['NetAmount'], r['Currency'], rates)
sh=wb['Summary']
for idx,p in enumerate(sorted(summary), 5):
    set_text(sh.cell(idx,1), p)
    for col,key in enumerate(['OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'], 2): set_amount(sh.cell(idx,col), summary[p][key])
last=max(5,4+len(summary))
for col in range(2,6):
    letter=get_column_letter(col); sh.cell(2,col).value=f'=SUM({letter}5:{letter}{last})'; sh.cell(2,col).number_format='0.00'

exceptions=[]
for r in orders:
    if r['Status']=='Cancelled': exceptions.append(('Orders',r['OrderID'],r['ProjectID'],'Cancelled order in period'))
    elif r['Status']=='Open': exceptions.append(('Orders',r['OrderID'],r['ProjectID'],'Open order requiring follow-up'))
for r in invoices:
    bal=Decimal(r['Balance']); due=date.fromisoformat(r['DueDate'])
    if bal>0 and due<TODAY: exceptions.append(('Invoices',r['InvoiceID'],r['ProjectID'],'Overdue unpaid balance'))
    elif bal>0: exceptions.append(('Invoices',r['InvoiceID'],r['ProjectID'],'Unpaid balance'))
for r in expenses:
    if r['Status']!='Approved': exceptions.append(('Expenses',r['ExpenseID'],r['ProjectID'],f"Expense status {r['Status']}"))
    if str(r.get('MissingReceipt','')).lower()=='true': exceptions.append(('Expenses',r['ExpenseID'],r['ProjectID'],'Missing receipt'))
for r in quotes:
    vu=date.fromisoformat(r['ValidUntil'])
    if r['Status']=='Expired': exceptions.append(('Quotes',r['QuoteID'],r['ProjectID'],'Expired quote'))
    elif r['Status']=='Sent' and vu<TODAY: exceptions.append(('Quotes',r['QuoteID'],r['ProjectID'],'Sent quote past valid-until date'))
    elif r['Status']=='Draft': exceptions.append(('Quotes',r['QuoteID'],r['ProjectID'],'Draft quote not sent'))
sh=wb['Exceptions']
for i,(src,doc,proj,reason) in enumerate(exceptions, 5):
    set_text(sh.cell(i,1), src); set_text(sh.cell(i,2), doc); set_text(sh.cell(i,3), proj); set_text(sh.cell(i,4), reason)
fill=PatternFill('solid', fgColor='FFF2CC')
exc_docs={doc for _,doc,_,_ in exceptions}
for s in ['Orders','Invoices','Expenses','Quotes']:
    sh=wb[s]
    for rr in range(5, sh.max_row+1):
        if str(sh.cell(rr,1).value) in exc_docs:
            for c in range(1, sh.max_column+1): sh.cell(rr,c).fill=fill

sh=wb['Report']
sh['B3']=START; sh['D3']=END
sh['B4']=f'CustomerID={CUSTOMER}; 上個月資料；所有金額依 input/fx_rates.csv 換算為 TWD'
now=datetime.now().isoformat(timespec='seconds')
sh['B5']=now; sh['B7']='Lab ERP; Expense Viewer; quote_cli; fx_rates.csv'; sh['D7']=now
sh['B9']=f"含訂單 {len(orders)} 筆、發票 {len(invoices)} 筆、費用 {len(expenses)} 筆、報價 {len(quotes)} 筆。Exceptions 工作表列出 {len(exceptions)} 個需要關注項目；Summary：Cancelled 訂單不計入 OrderTWD，ApprovedExpenseTWD 只計 Approved，AcceptedQuoteTWD 只計 Accepted。"

# column widths avoiding merged cells issue
for sh in wb.worksheets:
    for col_idx in range(1, sh.max_column+1):
        maxlen=0
        for row in range(1, min(sh.max_row,80)+1):
            v=sh.cell(row,col_idx).value
            if v is not None: maxlen=max(maxlen, len(str(v)))
        if maxlen: sh.column_dimensions[get_column_letter(col_idx)].width=min(max(maxlen+2,10),60)

out_xlsx=out/'C001_project_report_2026-09_TWD.xlsx'
wb.save(out_xlsx)
print('Saved', out_xlsx)

# Verification reopen every output file and confirm requirements
print('\nVerification from saved outputs:')
for p in [out/'orders_C001_2026-09.csv', out/'invoices_C001_2026-09.csv', out/'quotes_C001_2026-09.json', out/'expenses_P001_2026-09.csv', out/'expenses_P003_2026-09.csv', out_xlsx]:
    print('file', p.name, 'exists', p.exists(), 'bytes', p.stat().st_size if p.exists() else 'NA')
wb2=load_workbook(out_xlsx, data_only=False)
expected_counts={'Orders':len(orders),'Invoices':len(invoices),'Expenses':len(expenses),'Quotes':len(quotes),'Summary':len(summary),'Exceptions':len(exceptions)}
for s,n in expected_counts.items():
    sh=wb2[s]
    cnt=sum(1 for r in range(5, sh.max_row+1) if sh.cell(r,1).value not in (None,''))
    print(s, 'row_count', cnt, 'expected', n, 'OK' if cnt==n else 'FAIL')
    if cnt!=n: raise SystemExit('row count verification failed')
for s, idcols, amountcols in [('Orders',[1,2,3],[7,8]),('Invoices',[1,2,3,4],[8,9,10,11]),('Expenses',[1,2,3],[7,8]),('Quotes',[1,2,3],[8,9])]:
    sh=wb2[s]; ok=True
    for rr in range(5, sh.max_row+1):
        for c in idcols: ok=ok and isinstance(sh.cell(rr,c).value, str)
        for c in amountcols: ok=ok and isinstance(sh.cell(rr,c).value, (int,float))
    print(s, 'ID text and numeric amount types', 'OK' if ok else 'FAIL')
    if not ok: raise SystemExit('type verification failed')
headers_ok=True
for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    sh=wb2[s]
    headers=[sh.cell(4,c).value for c in range(1, sh.max_column+1)]
    ok=all(h not in (None,'') for h in headers)
    print(s, 'headers', headers, 'OK' if ok else 'FAIL')
    headers_ok=headers_ok and ok
if not headers_ok: raise SystemExit('header verification failed')
print('Report period:', wb2['Report']['B3'].value, wb2['Report']['D3'].value)
print('Summary totals:')
for p,v in summary.items(): print(p, {k:str(money(val)) for k,val in v.items()})
print('Exceptions count', len(exceptions))
for e in exceptions: print(e)
