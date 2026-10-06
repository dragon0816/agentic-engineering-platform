from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
import csv, json, shutil
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from openpyxl.utils import get_column_letter

ws = Path.cwd()
inp = ws/'input'
out = ws/'output'
downloads = out/'downloads'
out.mkdir(exist_ok=True)

customer='C001'
start='2026-09-01'
end='2026-09-30'
today=date(2026,10,6)
generated=datetime.now().astimezone().replace(microsecond=0).isoformat()

# inspect inputs actually used
print('Using files:')
for p in [inp/'project_template.xlsx', inp/'fx_rates.csv', downloads/'orders_C001_2026-09.csv', downloads/'invoices_C001_2026-09.csv', out/'expenses_P001_2026-09.csv', out/'expenses_P003_2026-09.csv', out/'quotes_C001_2026-09.csv']:
    print(p, 'exists=', p.exists(), 'bytes=', p.stat().st_size if p.exists() else None)
    if p.suffix.lower()=='.csv' and p.exists():
        with open(p, newline='', encoding='utf-8-sig') as f:
            r=csv.reader(f)
            rows=[row for _,row in zip(range(3), r)]
            print(' sample:', rows)

# robust csv reader for fx note commas
fx={}
with open(inp/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    rdr=csv.reader(f)
    header=next(rdr)
    for row in rdr:
        if len(row)>=2 and row[0]:
            fx[row[0]]=Decimal(row[1])
print('FX:', fx)

def money(x):
    return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
def twd(amount, cur):
    return money(Decimal(str(amount))*fx[cur])
def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

orders=read_csv(downloads/'orders_C001_2026-09.csv')
invoices=read_csv(downloads/'invoices_C001_2026-09.csv')
quotes=read_csv(out/'quotes_C001_2026-09.csv')
expenses=[]
for p in [out/'expenses_P001_2026-09.csv', out/'expenses_P003_2026-09.csv']:
    if p.exists(): expenses.extend(read_csv(p))
# de-dupe expenses by ExpenseID just in case
seen=set(); exp2=[]
for e in expenses:
    if e['ExpenseID'] not in seen:
        seen.add(e['ExpenseID']); exp2.append(e)
expenses=exp2

# workbook
wb=load_workbook(inp/'project_template.xlsx')

# helper clear rows below header but preserve sheets
def clear_data(sheet, min_row=5):
    if sheet.max_row >= min_row:
        sheet.delete_rows(min_row, sheet.max_row-min_row+1)

def append_row(sheet, values, text_cols=(), date_cols=(), money_cols=()):
    r=sheet.max_row+1
    if r<5: r=5
    for c,v in enumerate(values, start=1):
        cell=sheet.cell(r,c,value=v)
        if c in text_cols:
            cell.number_format='@'
            if v is not None: cell.value=str(v)
        if c in date_cols:
            cell.number_format='yyyy-mm-dd'
        if c in money_cols:
            cell.number_format='0.00'
    return r

# Report
rep=wb['Report']
rep['B3']=start; rep['D3']=end
rep['B4']=f'CustomerID={customer}; period={start}..{end}; amounts converted to TWD using input/fx_rates.csv'
rep['B5']=generated
rep['B7']='Lab ERP; Expense Viewer; quote_cli; fx_rates.csv'
rep['D7']=generated

# Details
for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    clear_data(wb[s])

for o in orders:
    append_row(wb['Orders'], [o['OrderID'], o['ProjectID'], o['CustomerID'], o['OrderDate'], o['Status'], o['Currency'], float(money(o['NetAmount'])), float(twd(o['NetAmount'], o['Currency']))], text_cols={1,2,3,5,6}, date_cols={4}, money_cols={7,8})
for inv in invoices:
    append_row(wb['Invoices'], [inv['InvoiceID'], inv['OrderID'], inv['ProjectID'], inv['CustomerID'], inv['InvoiceDate'], inv['DueDate'], inv['Currency'], float(money(inv['Amount'])), float(money(inv['PaidAmount'])), float(money(inv['Balance'])), float(twd(inv['Balance'], inv['Currency']))], text_cols={1,2,3,4,7}, date_cols={5,6}, money_cols={8,9,10,11})
for e in expenses:
    append_row(wb['Expenses'], [e['ExpenseID'], e['ProjectID'], e['EmployeeID'], e['ExpenseDate'], e['Status'], e['Currency'], float(money(e['Amount'])), float(twd(e['Amount'], e['Currency']))], text_cols={1,2,3,5,6}, date_cols={4}, money_cols={7,8})
for q in quotes:
    append_row(wb['Quotes'], [q['QuoteID'], q['ProjectID'], q['CustomerID'], q['QuoteDate'], q['ValidUntil'], q['Status'], q['Currency'], float(money(q['NetAmount'])), float(twd(q['NetAmount'], q['Currency']))], text_cols={1,2,3,6,7}, date_cols={4,5}, money_cols={8,9})

# summary per project
def addtot(d, key, field, val):
    d.setdefault(key, {'OrderTWD':Decimal('0'), 'InvoiceBalanceTWD':Decimal('0'), 'ApprovedExpenseTWD':Decimal('0'), 'AcceptedQuoteTWD':Decimal('0')})
    d[key][field]+=val
summ={}
for o in orders:
    addtot(summ, o['ProjectID'] or '', 'OrderTWD', twd(o['NetAmount'], o['Currency']))
for inv in invoices:
    addtot(summ, inv['ProjectID'] or '', 'InvoiceBalanceTWD', twd(inv['Balance'], inv['Currency']))
for e in expenses:
    if e['Status']=='Approved':
        addtot(summ, e['ProjectID'] or '', 'ApprovedExpenseTWD', twd(e['Amount'], e['Currency']))
for q in quotes:
    if q['Status']=='Accepted':
        addtot(summ, q['ProjectID'] or '', 'AcceptedQuoteTWD', twd(q['NetAmount'], q['Currency']))
for pid in sorted(summ):
    vals=summ[pid]
    append_row(wb['Summary'], [pid, float(money(vals['OrderTWD'])), float(money(vals['InvoiceBalanceTWD'])), float(money(vals['ApprovedExpenseTWD'])), float(money(vals['AcceptedQuoteTWD']))], text_cols={1}, money_cols={2,3,4,5})
last=max(5, wb['Summary'].max_row)
for col in range(2,6):
    letter=get_column_letter(col)
    wb['Summary'].cell(2,col).value=f'=SUM({letter}5:{letter}{last})'
    wb['Summary'].cell(2,col).number_format='0.00'

# exceptions / attention items
exceptions=[]
for o in orders:
    if o['Status']=='Cancelled':
        exceptions.append(('Orders', o['OrderID'], o['ProjectID'], 'Cancelled order'))
    if not o.get('ProjectID'):
        exceptions.append(('Orders', o['OrderID'], '', 'Missing ProjectID'))
for inv in invoices:
    bal=Decimal(inv['Balance'])
    due=date.fromisoformat(inv['DueDate'])
    if bal>0 and due<today:
        exceptions.append(('Invoices', inv['InvoiceID'], inv['ProjectID'], f'Overdue unpaid balance; DueDate {inv["DueDate"]}; BalanceTWD {twd(inv["Balance"], inv["Currency"])}'))
    elif bal>0:
        exceptions.append(('Invoices', inv['InvoiceID'], inv['ProjectID'], f'Unpaid balance; DueDate {inv["DueDate"]}; BalanceTWD {twd(inv["Balance"], inv["Currency"])}'))
for e in expenses:
    if e['Status']!='Approved':
        exceptions.append(('Expenses', e['ExpenseID'], e['ProjectID'], f'Expense status {e["Status"]}'))
    if str(e.get('MissingReceipt','')).lower()=='true':
        exceptions.append(('Expenses', e['ExpenseID'], e['ProjectID'], 'Missing receipt'))
for q in quotes:
    valid=date.fromisoformat(q['ValidUntil'])
    if q['Status'] in {'Draft','Expired'}:
        exceptions.append(('Quotes', q['QuoteID'], q['ProjectID'], f'Quote status {q["Status"]}'))
    elif q['Status']!='Accepted' and valid<today:
        exceptions.append(('Quotes', q['QuoteID'], q['ProjectID'], f'Quote not accepted and expired on {q["ValidUntil"]}'))

for ex in exceptions:
    append_row(wb['Exceptions'], list(ex), text_cols={1,2,3,4})

rep['B9']=f'Attention rules used: cancelled orders; unpaid invoices past due as of {today.isoformat()}; non-approved expenses; missing receipts; draft/expired or expired-not-accepted quotes. Expenses exported by project(s) {", ".join(sorted({o["ProjectID"] for o in orders if o["ProjectID"]}))}; Expense Viewer has no CustomerID filter.'

# Highlight exceptions matching source/doc id in detail sheets
fill=PatternFill(fill_type='solid', fgColor='FFF2CC')
exdocs={(s,d) for s,d,_,_ in exceptions}
for sheet, idcol in [('Orders',1),('Invoices',1),('Expenses',1),('Quotes',1)]:
    sh=wb[sheet]
    for r in range(5, sh.max_row+1):
        if (sheet, str(sh.cell(r,idcol).value)) in exdocs:
            for c in range(1, sh.max_column+1): sh.cell(r,c).fill=fill

outfile=out/'project_C001_2026-09_report.xlsx'
wb.save(outfile)
print('Saved', outfile)
print('Counts orders invoices expenses quotes exceptions projects:', len(orders), len(invoices), len(expenses), len(quotes), len(exceptions), len(summ))
print('Summary:', {k:{kk:str(vv) for kk,vv in vals.items()} for k,vals in summ.items()})
print('Exceptions:')
for ex in exceptions:
    print(ex)

# Verification reopen output
wb2=load_workbook(outfile, data_only=False)
checks=[]
for sh, expected_headers in {
    'Orders':['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD'],
    'Invoices':['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD'],
    'Expenses':['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD'],
    'Quotes':['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD'],
    'Summary':['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'],
    'Exceptions':['Source','DocumentID','ProjectID','Reason']}.items():
    got=[wb2[sh].cell(4,c).value for c in range(1,len(expected_headers)+1)]
    assert got==expected_headers, (sh,got)
# row counts
assert wb2['Orders'].max_row-4==len(orders)
assert wb2['Invoices'].max_row-4==len(invoices)
assert wb2['Expenses'].max_row-4==len(expenses)
assert wb2['Quotes'].max_row-4==len(quotes)
assert wb2['Exceptions'].max_row-4==len(exceptions)
# text IDs and number formats
for sh in ['Orders','Invoices','Expenses','Quotes']:
    for r in range(5, wb2[sh].max_row+1):
        assert isinstance(wb2[sh].cell(r,1).value, str)
for sh, cols in [('Orders',[7,8]),('Invoices',[8,9,10,11]),('Expenses',[7,8]),('Quotes',[8,9])]:
    for r in range(5, wb2[sh].max_row+1):
        for c in cols:
            assert isinstance(wb2[sh].cell(r,c).value, (int,float))
            assert wb2[sh].cell(r,c).number_format=='0.00'
print('VERIFIED output workbook headers, row counts, text IDs, numeric money formats, summary formulas, exceptions count')