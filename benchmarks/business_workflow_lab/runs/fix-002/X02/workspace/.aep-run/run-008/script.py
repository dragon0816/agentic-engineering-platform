from pathlib import Path
from openpyxl import load_workbook
from openpyxl.styles import PatternFill, Font
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
import csv, json, re, shutil

ws=Path.cwd(); inp=ws/'input'; out=ws/'output'; out.mkdir(exist_ok=True)
print('Preparing workbook from raw files:')
for p in sorted(out.glob('*C001_2026-09*')):
    print('-', p.name, p.stat().st_size)
for p in sorted(out.glob('expenses_P*_2026-09.csv')):
    print('-', p.name, p.stat().st_size)

START='2026-09-01'; END='2026-09-30'; CUSTOMER='C001'; TODAY=date(2026,10,6)
Q=Decimal('0.01')
def money(x):
    return Decimal(str(x)).quantize(Q, rounding=ROUND_HALF_UP)
def twd(amount,currency,rates):
    return money(Decimal(str(amount))*rates[currency])

def read_csv_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))
# rates (csv has unquoted commas in note; first 2 cols OK)
rates={}
with open(inp/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    r=csv.reader(f)
    next(r)
    for row in r:
        if row:
            rates[row[0]]=Decimal(row[1])
print('Rates:', rates)
orders=read_csv_rows(out/'orders_C001_2026-09.csv')
invoices=read_csv_rows(out/'invoices_C001_2026-09.csv')
quotes=json.loads((out/'quotes_C001_2026-09.json').read_text(encoding='utf-8'))['items']
projects=sorted({r['ProjectID'] for r in orders} | {r['ProjectID'] for r in invoices} | {r['ProjectID'] for r in quotes})
expenses=[]
for proj in projects:
    p=out/f'expenses_{proj}_2026-09.csv'
    if p.exists():
        expenses.extend(read_csv_rows(p))
print('counts raw orders/invoices/expenses/quotes', len(orders), len(invoices), len(expenses), len(quotes), 'projects', projects)

# Load template
wb=load_workbook(inp/'project_template.xlsx')
# clear existing data rows from detail sheets (row 5+)
for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    sh=wb[s]
    if sh.max_row>=5:
        sh.delete_rows(5, sh.max_row-4)

def set_text(cell, value):
    cell.value = '' if value is None else str(value)
    cell.number_format='@'
def set_date_text(cell, value):
    cell.value=str(value)
    cell.number_format='yyyy-mm-dd'
def set_amount(cell, value):
    cell.value=float(money(value))
    cell.number_format='0.00'

def apply_text_format(row, cols):
    for c in cols:
        row[c-1].number_format='@'

# Orders sheet
sh=wb['Orders']
for i,r in enumerate(orders, start=5):
    set_text(sh.cell(i,1), r['OrderID'])
    set_text(sh.cell(i,2), r['ProjectID'])
    set_text(sh.cell(i,3), r['CustomerID'])
    set_date_text(sh.cell(i,4), r['OrderDate'])
    set_text(sh.cell(i,5), r['Status'])
    set_text(sh.cell(i,6), r['Currency'])
    set_amount(sh.cell(i,7), r['NetAmount'])
    set_amount(sh.cell(i,8), twd(r['NetAmount'], r['Currency'], rates))
# Invoices
sh=wb['Invoices']
for i,r in enumerate(invoices, start=5):
    set_text(sh.cell(i,1), r['InvoiceID'])
    set_text(sh.cell(i,2), r['OrderID'])
    set_text(sh.cell(i,3), r['ProjectID'])
    set_text(sh.cell(i,4), r['CustomerID'])
    set_date_text(sh.cell(i,5), r['InvoiceDate'])
    set_date_text(sh.cell(i,6), r['DueDate'])
    set_text(sh.cell(i,7), r['Currency'])
    set_amount(sh.cell(i,8), r['Amount'])
    set_amount(sh.cell(i,9), r['PaidAmount'])
    bal=money(Decimal(r['Amount'])-Decimal(r['PaidAmount']))
    set_amount(sh.cell(i,10), bal)
    set_amount(sh.cell(i,11), twd(bal, r['Currency'], rates))
# Expenses sorted by date/id
expenses.sort(key=lambda r:(r['ProjectID'], r['ExpenseDate'], r['ExpenseID']))
sh=wb['Expenses']
for i,r in enumerate(expenses, start=5):
    set_text(sh.cell(i,1), r['ExpenseID'])
    set_text(sh.cell(i,2), r['ProjectID'])
    set_text(sh.cell(i,3), r['EmployeeID'])
    set_date_text(sh.cell(i,4), r['ExpenseDate'])
    set_text(sh.cell(i,5), r['Status'])
    set_text(sh.cell(i,6), r['Currency'])
    set_amount(sh.cell(i,7), r['Amount'])
    set_amount(sh.cell(i,8), twd(r['Amount'], r['Currency'], rates))
# Quotes
sh=wb['Quotes']
for i,r in enumerate(quotes, start=5):
    set_text(sh.cell(i,1), r['QuoteID'])
    set_text(sh.cell(i,2), r['ProjectID'])
    set_text(sh.cell(i,3), r['CustomerID'])
    set_date_text(sh.cell(i,4), r['QuoteDate'])
    set_date_text(sh.cell(i,5), r['ValidUntil'])
    set_text(sh.cell(i,6), r['Status'])
    set_text(sh.cell(i,7), r['Currency'])
    set_amount(sh.cell(i,8), r['NetAmount'])
    set_amount(sh.cell(i,9), twd(r['NetAmount'], r['Currency'], rates))

# Summary
summary={p:{'OrderTWD':Decimal('0'),'InvoiceBalanceTWD':Decimal('0'),'ApprovedExpenseTWD':Decimal('0'),'AcceptedQuoteTWD':Decimal('0')} for p in projects}
for r in orders:
    if r['Status']!='Cancelled':
        summary[r['ProjectID']]['OrderTWD']+=twd(r['NetAmount'], r['Currency'], rates)
for r in invoices:
    bal=money(Decimal(r['Amount'])-Decimal(r['PaidAmount']))
    summary[r['ProjectID']]['InvoiceBalanceTWD']+=twd(bal, r['Currency'], rates)
for r in expenses:
    if r['Status']=='Approved':
        summary[r['ProjectID']]['ApprovedExpenseTWD']+=twd(r['Amount'], r['Currency'], rates)
for r in quotes:
    if r['Status']=='Accepted':
        summary[r['ProjectID']]['AcceptedQuoteTWD']+=twd(r['NetAmount'], r['Currency'], rates)
sh=wb['Summary']
for idx,p in enumerate(sorted(summary), start=5):
    set_text(sh.cell(idx,1), p)
    for col,key in enumerate(['OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'], start=2):
        set_amount(sh.cell(idx,col), summary[p][key])
last=max(5,4+len(summary))
for col in range(2,6):
    letter=chr(ord('A')+col-1)
    sh.cell(2,col).value=f'=SUM({letter}5:{letter}{last})'
    sh.cell(2,col).number_format='0.00'

# Exceptions/focus items
exceptions=[]
# orders: cancelled/open
for r in orders:
    if r['Status']=='Cancelled':
        exceptions.append(('Orders',r['OrderID'],r['ProjectID'],'Cancelled order in period'))
    elif r['Status']=='Open':
        exceptions.append(('Orders',r['OrderID'],r['ProjectID'],'Open order requiring follow-up'))
# invoices: balance>0 and overdue/on due? overdue today 2026-10-06
for r in invoices:
    bal=Decimal(r['Balance'])
    due=date.fromisoformat(r['DueDate'])
    if bal>0 and due<TODAY:
        exceptions.append(('Invoices',r['InvoiceID'],r['ProjectID'],'Overdue unpaid balance'))
    elif bal>0:
        exceptions.append(('Invoices',r['InvoiceID'],r['ProjectID'],'Unpaid balance'))
# expenses: non-approved and missing receipt
for r in expenses:
    if r['Status']!='Approved':
        exceptions.append(('Expenses',r['ExpenseID'],r['ProjectID'],f"Expense status {r['Status']}"))
    if str(r.get('MissingReceipt','')).lower()=='true':
        exceptions.append(('Expenses',r['ExpenseID'],r['ProjectID'],'Missing receipt'))
# quotes: accepted not exception? sent expired draft follow-up
for r in quotes:
    vu=date.fromisoformat(r['ValidUntil'])
    if r['Status']=='Expired':
        exceptions.append(('Quotes',r['QuoteID'],r['ProjectID'],'Expired quote'))
    elif r['Status']=='Sent' and vu<TODAY:
        exceptions.append(('Quotes',r['QuoteID'],r['ProjectID'],'Sent quote past valid-until date'))
    elif r['Status']=='Draft':
        exceptions.append(('Quotes',r['QuoteID'],r['ProjectID'],'Draft quote not sent'))
sh=wb['Exceptions']
for i,(src,doc,proj,reason) in enumerate(exceptions, start=5):
    set_text(sh.cell(i,1), src); set_text(sh.cell(i,2), doc); set_text(sh.cell(i,3), proj); set_text(sh.cell(i,4), reason)
# Highlight attention items rows in detail sheets corresponding to exceptions
fill=PatternFill('solid', fgColor='FFF2CC')
exc_docs={doc for _,doc,_,_ in exceptions}
for s, idcol in [('Orders',1),('Invoices',1),('Expenses',1),('Quotes',1)]:
    sh=wb[s]
    for row in range(5, sh.max_row+1):
        if str(sh.cell(row,idcol).value) in exc_docs:
            for c in range(1, sh.max_column+1):
                sh.cell(row,c).fill=fill

# Report metadata
sh=wb['Report']
sh['B3']=START; sh['D3']=END
sh['B4']=f'CustomerID={CUSTOMER}; last month from {START} to {END}; amounts converted to TWD using input/fx_rates.csv'
sh['B5']=datetime.now().isoformat(timespec='seconds')
sh['B7']='Lab ERP; Expense Viewer; quote_cli; fx_rates.csv'
sh['D7']=datetime.now().isoformat(timespec='seconds')
sh['B9']=f"含訂單 {len(orders)} 筆、發票 {len(invoices)} 筆、費用 {len(expenses)} 筆、報價 {len(quotes)} 筆。Exceptions 工作表列出 {len(exceptions)} 個需要關注項目；Summary 已排除 Cancelled 訂單，ApprovedExpenseTWD 只計 Approved 費用，AcceptedQuoteTWD 只計 Accepted 報價。"

# autosize-ish
for sh in wb.worksheets:
    for col in sh.columns:
        letter=col[0].column_letter
        maxlen=max(len(str(c.value)) if c.value is not None else 0 for c in col[:80])
        if maxlen:
            sh.column_dimensions[letter].width=min(max(maxlen+2,10),50)

out_xlsx=out/'C001_project_report_2026-09_TWD.xlsx'
wb.save(out_xlsx)
print('Saved', out_xlsx)

# Verification reopen every output relevant
wb2=load_workbook(out_xlsx, data_only=False)
checks=[]
expected_counts={'Orders':len(orders),'Invoices':len(invoices),'Expenses':len(expenses),'Quotes':len(quotes),'Summary':len(summary),'Exceptions':len(exceptions)}
for s,n in expected_counts.items():
    sh=wb2[s]
    # count nonempty col A row 5+
    cnt=sum(1 for r in range(5, sh.max_row+1) if sh.cell(r,1).value not in (None,''))
    checks.append((s,cnt,n,'OK' if cnt==n else 'FAIL'))
# Headers match
for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    sh=wb2[s]
    headers=[sh.cell(4,c).value for c in range(1, sh.max_column+1)]
    checks.append((s+' headers', headers, 'present', 'OK' if all(headers) else 'FAIL'))
# ID text format, amount numeric
for s, idcols, amountcols in [('Orders',[1,2,3],[7,8]),('Invoices',[1,2,3,4],[8,9,10,11]),('Expenses',[1,2,3],[7,8]),('Quotes',[1,2,3],[8,9])]:
    sh=wb2[s]; ok=True
    for r in range(5, sh.max_row+1):
        for c in idcols:
            ok = ok and isinstance(sh.cell(r,c).value, str)
        for c in amountcols:
            ok = ok and isinstance(sh.cell(r,c).value, (int,float))
    checks.append((s+' types', '', '', 'OK' if ok else 'FAIL'))
print('Verification:')
for c in checks: print(c)
if any(c[-1]!='OK' for c in checks): raise SystemExit('verification failed')
print('Summary totals:')
for p,v in summary.items(): print(p, {k:str(money(val)) for k,val in v.items()})
print('Exceptions count', len(exceptions))
for e in exceptions: print(e)
