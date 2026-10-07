from pathlib import Path
import csv, json, subprocess, sys, shutil, os
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from copy import copy
from openpyxl import load_workbook

ws = Path.cwd()
input_dir = ws/'input'
out_dir = ws/'output'
dl_dir = out_dir/'downloads'
out_dir.mkdir(exist_ok=True)

CUSTOMER='C001'
FROM='2026-09-01'
TO='2026-09-30'
CUTOFF=date.fromisoformat('2026-09-30')
GENERATED=datetime.now().replace(microsecond=0).isoformat()

# Helpers
TWOPLACES = Decimal('0.01')
def money(x):
    return Decimal(str(x)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
def twd(amount, currency, rates):
    if currency not in rates:
        raise ValueError(f'Missing FX rate for {currency}')
    return (Decimal(str(amount)) * rates[currency]).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
def parse_date(s):
    if s in (None, ''):
        return None
    return date.fromisoformat(str(s))
def read_csv(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))
def set_row(wsht, row_num, values, text_cols=(), date_cols=(), money_cols=()):
    for col_idx, val in enumerate(values, start=1):
        c=wsht.cell(row=row_num, column=col_idx)
        c.value=val
        # copy style/format from row 4 (header has visual style, but use basic formats below)
        if col_idx in text_cols:
            c.number_format='@'
        if col_idx in date_cols:
            c.number_format='yyyy-mm-dd'
        if col_idx in money_cols:
            c.number_format='0.00'

def clear_data(wsht, min_row=5):
    max_row = wsht.max_row
    if max_row >= min_row:
        wsht.delete_rows(min_row, max_row-min_row+1)

# Read rates; csv notes contain commas, accept first two cols.
rates={}
with open(input_dir/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    rdr=csv.reader(f)
    headers=next(rdr)
    for row in rdr:
        if not row or not row[0]: continue
        rates[row[0]]=Decimal(row[1])
print('FX rates:', rates)

# Read ERP downloads
orders_raw=read_csv(dl_dir/'orders_C001_2026-09.csv')
invoices_raw=read_csv(dl_dir/'invoices_C001_2026-09.csv')
print('raw orders', len(orders_raw), 'raw invoices', len(invoices_raw))

orders=[]
for r in orders_raw:
    if r['CustomerID']==CUSTOMER and FROM <= r['OrderDate'] <= TO and r['Status'] != 'Cancelled':
        orders.append({
            'OrderID': r['OrderID'], 'ProjectID': r['ProjectID'], 'CustomerID': r['CustomerID'],
            'OrderDate': parse_date(r['OrderDate']), 'Status': r['Status'], 'Currency': r['Currency'],
            'NetAmount': money(r['NetAmount']), 'AmountTWD': twd(r['NetAmount'], r['Currency'], rates)
        })

invoices=[]
for r in invoices_raw:
    if r['CustomerID']==CUSTOMER and FROM <= r['InvoiceDate'] <= TO:
        invoices.append({
            'InvoiceID': r['InvoiceID'], 'OrderID': r['OrderID'], 'ProjectID': r['ProjectID'], 'CustomerID': r['CustomerID'],
            'InvoiceDate': parse_date(r['InvoiceDate']), 'DueDate': parse_date(r['DueDate']), 'Currency': r['Currency'],
            'Amount': money(r['Amount']), 'PaidAmount': money(r['PaidAmount']), 'Balance': money(r['Balance']),
            'BalanceTWD': twd(r['Balance'], r['Currency'], rates)
        })

# Quotes via CLI
cli = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py'
cmd=[sys.executable, cli, 'quotes','list','--customer',CUSTOMER,'--from',FROM,'--to',TO,'--format','json']
proc=subprocess.run(cmd, capture_output=True, text=True)
if proc.returncode != 0:
    raise RuntimeError(f'quote_cli failed {proc.returncode}: {proc.stderr}')
qdata=json.loads(proc.stdout)
quotes=[]
for r in qdata['items']:
    quotes.append({
        'QuoteID': r['QuoteID'], 'ProjectID': r['ProjectID'], 'CustomerID': r['CustomerID'],
        'QuoteDate': parse_date(r['QuoteDate']), 'ValidUntil': parse_date(r['ValidUntil']), 'Status': r['Status'],
        'Currency': r['Currency'], 'NetAmount': money(r['NetAmount']), 'AmountTWD': twd(r['NetAmount'], r['Currency'], rates)
    })
print('quotes', len(quotes))

# Determine C001 corresponding projects from orders/invoices/quotes last month
projects = sorted({r['ProjectID'] for r in orders+invoices+quotes if r.get('ProjectID')})
print('projects for expenses', projects)

# Read exported approved expenses for these projects (already collected via desktop)
expenses=[]
for project in projects:
    p=out_dir/f'expenses_{project}_Approved_2026-09.csv'
    if not p.exists():
        print('WARNING missing expense export', p.name)
        continue
    for r in read_csv(p):
        if r['ProjectID']==project and FROM <= r['ExpenseDate'] <= TO and r['Status']=='Approved':
            expenses.append({
                'ExpenseID': r['ExpenseID'], 'ProjectID': r['ProjectID'], 'EmployeeID': r['EmployeeID'],
                'ExpenseDate': parse_date(r['ExpenseDate']), 'Status': r['Status'], 'Currency': r['Currency'],
                'Amount': money(r['Amount']), 'AmountTWD': twd(r['Amount'], r['Currency'], rates),
                'ReceiptID': r.get('ReceiptID',''), 'MissingReceipt': str(r.get('MissingReceipt','')).lower()=='true'
            })
print('expenses', len(expenses))

# Sort stable
orders.sort(key=lambda r:(r['OrderDate'], r['OrderID']))
invoices.sort(key=lambda r:(r['InvoiceDate'], r['InvoiceID']))
expenses.sort(key=lambda r:(r['ExpenseDate'], r['ExpenseID']))
quotes.sort(key=lambda r:(r['QuoteDate'], r['QuoteID']))

# Exceptions
exceptions=[]
for r in invoices:
    # As of cutoff: due date on or before cutoff and balance remains unpaid.
    if r['DueDate'] and r['DueDate'] <= CUTOFF and r['Balance'] > 0:
        exceptions.append(('Invoices', r['InvoiceID'], r['ProjectID'], f"Overdue unpaid invoice as of {TO}: DueDate {r['DueDate'].isoformat()}, Balance {r['Balance']} {r['Currency']}"))
for r in expenses:
    if r['MissingReceipt'] or not r['ReceiptID']:
        exceptions.append(('Expenses', r['ExpenseID'], r['ProjectID'], 'Approved expense missing receipt'))
for r in quotes:
    if r['ValidUntil'] and r['ValidUntil'] < CUTOFF and r['Status'] != 'Accepted':
        exceptions.append(('Quotes', r['QuoteID'], r['ProjectID'], f"Quote ValidUntil {r['ValidUntil'].isoformat()} is before {TO} and status is {r['Status']}"))
print('exceptions', len(exceptions))

# Fill workbook copy
src=input_dir/'project_template.xlsx'
out=out_dir/'project_report_C001_2026-09_TWD.xlsx'
shutil.copy2(src, out)
wb=load_workbook(out)

# Report
rep=wb['Report']
rep['B3']=FROM
rep['D3']=TO
rep['B4']='Customer C001; orders exclude Cancelled; invoices by invoice date; expenses Approved only for C001-related projects; quotes all statuses; FX from input/fx_rates.csv.'
rep['B5']=GENERATED
rep['B7']='Lab ERP; Expense Viewer; quote_cli; fx_rates.csv'
rep['D7']=GENERATED
rep['B9']='Attention: invoices with DueDate <= 2026-09-30 and Balance > 0; approved expenses missing receipt; quotes ValidUntil < 2026-09-30 and Status != Accepted. No live FX used.'

# Clear and write detail sheets
for name in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    clear_data(wb[name], 5)

for i,r in enumerate(orders, start=5):
    set_row(wb['Orders'], i, [r['OrderID'], r['ProjectID'], r['CustomerID'], r['OrderDate'], r['Status'], r['Currency'], r['NetAmount'], r['AmountTWD']], text_cols={1,2,3,5,6}, date_cols={4}, money_cols={7,8})
for i,r in enumerate(invoices, start=5):
    set_row(wb['Invoices'], i, [r['InvoiceID'], r['OrderID'], r['ProjectID'], r['CustomerID'], r['InvoiceDate'], r['DueDate'], r['Currency'], r['Amount'], r['PaidAmount'], r['Balance'], r['BalanceTWD']], text_cols={1,2,3,4,7}, date_cols={5,6}, money_cols={8,9,10,11})
for i,r in enumerate(expenses, start=5):
    set_row(wb['Expenses'], i, [r['ExpenseID'], r['ProjectID'], r['EmployeeID'], r['ExpenseDate'], r['Status'], r['Currency'], r['Amount'], r['AmountTWD']], text_cols={1,2,3,5,6}, date_cols={4}, money_cols={7,8})
for i,r in enumerate(quotes, start=5):
    set_row(wb['Quotes'], i, [r['QuoteID'], r['ProjectID'], r['CustomerID'], r['QuoteDate'], r['ValidUntil'], r['Status'], r['Currency'], r['NetAmount'], r['AmountTWD']], text_cols={1,2,3,6,7}, date_cols={4,5}, money_cols={8,9})

# Summary by project
summary_projects=sorted(set(projects) | {r['ProjectID'] for r in expenses})
for i,pid in enumerate(summary_projects, start=5):
    order_sum=sum((r['AmountTWD'] for r in orders if r['ProjectID']==pid), Decimal('0.00'))
    inv_sum=sum((r['BalanceTWD'] for r in invoices if r['ProjectID']==pid), Decimal('0.00'))
    exp_sum=sum((r['AmountTWD'] for r in expenses if r['ProjectID']==pid), Decimal('0.00'))
    quote_sum=sum((r['AmountTWD'] for r in quotes if r['ProjectID']==pid and r['Status']=='Accepted'), Decimal('0.00'))
    set_row(wb['Summary'], i, [pid, money(order_sum), money(inv_sum), money(exp_sum), money(quote_sum)], text_cols={1}, money_cols={2,3,4,5})
last=max(5, 4+len(summary_projects))
for col in 'BCDE':
    wb['Summary'][f'{col}2']=f'=SUM({col}5:{col}{last})'
    wb['Summary'][f'{col}2'].number_format='0.00'

for i,(source,doc,project,reason) in enumerate(exceptions, start=5):
    set_row(wb['Exceptions'], i, [source, doc, project, reason], text_cols={1,2,3,4})

# basic page/text number formats for detail money/date already set
wb.save(out)
print('saved', out)

# Verification: reopen saved output and validate stated requirements
wb2=load_workbook(out, data_only=False)
checks=[]
def sheet_rows(name):
    s=wb2[name]
    return list(s.iter_rows(min_row=5, max_row=s.max_row, values_only=True)) if s.max_row>=5 else []
orders2=sheet_rows('Orders')
invoices2=sheet_rows('Invoices')
expenses2=sheet_rows('Expenses')
quotes2=sheet_rows('Quotes')
exceptions2=sheet_rows('Exceptions')
summary2=sheet_rows('Summary')
checks.append(('orders_rows_excl_cancelled', len(orders2)==len(orders) and all(r[4] != 'Cancelled' for r in orders2)))
checks.append(('invoices_rows', len(invoices2)==len(invoices)))
checks.append(('expenses_approved_project_rows', len(expenses2)==len(expenses) and all(r[4]=='Approved' and r[1] in projects for r in expenses2)))
checks.append(('quotes_all_rows', len(quotes2)==len(quotes)))
checks.append(('exceptions_rows', len(exceptions2)==len(exceptions)))
checks.append(('ids_text_preserved', all(str(r[0]).startswith('0045') for r in orders2) and all(str(r[0]).startswith('0090') for r in invoices2)))
checks.append(('money_numeric', all(isinstance(r[7], (int,float,Decimal)) for r in orders2) and all(isinstance(r[10], (int,float,Decimal)) for r in invoices2)))
checks.append(('summary_formula_extended', wb2['Summary']['B2'].value==f'=SUM(B5:B{last})'))
print('CHECKS')
for name, ok in checks:
    print(name, 'OK' if ok else 'FAIL')
if not all(ok for _,ok in checks):
    raise SystemExit(1)
print('ROW_COUNTS', {'Orders':len(orders2),'Invoices':len(invoices2),'Expenses':len(expenses2),'Quotes':len(quotes2),'Summary':len(summary2),'Exceptions':len(exceptions2)})
print('EXCEPTIONS')
for r in exceptions2:
    print(r)
print('OUTPUT', out)
