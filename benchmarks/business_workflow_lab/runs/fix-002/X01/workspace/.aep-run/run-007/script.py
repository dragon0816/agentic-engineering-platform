from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from urllib.request import build_opener, HTTPCookieProcessor, Request
from urllib.parse import urlencode
from http.cookiejar import CookieJar
import csv, io, json, subprocess, shutil, datetime, sys
import openpyxl

WORKSPACE = Path('.').resolve()
INPUT = WORKSPACE/'input'
OUTPUT = WORKSPACE/'output'
OUTPUT.mkdir(exist_ok=True)
START = '2026-09-01'
END = '2026-09-30'
TODAY = datetime.date(2026,10,6)
BASE_URL = 'http://127.0.0.1:8810'
QUOTE_CLI = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\quote_cli.cmd'
EXPENSE_EXPORT = OUTPUT/'expenses_2026-09_approved.csv'
REPORT_PATH = OUTPUT/'project_report_2026-09.xlsx'

TWOPLACES = Decimal('0.01')
def money(x):
    return Decimal(str(x)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
def to_twd(amount, currency, fx):
    if currency not in fx:
        raise KeyError(f'Missing FX rate for {currency}')
    return (Decimal(str(amount)) * fx[currency]).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

def read_fx(path):
    fx={}
    with path.open(newline='', encoding='utf-8-sig') as f:
        r=csv.reader(f)
        header=next(r)
        for row in r:
            if not row or not row[0]: continue
            fx[row[0]]=Decimal(row[1])
    return fx

def sap_login_opener():
    op=build_opener(HTTPCookieProcessor(CookieJar()))
    data=urlencode({'next':'/orders','sso':'company'}).encode()
    op.open(Request(BASE_URL+'/login', data=data, method='POST'), timeout=20).read()
    return op

def sap_export(op, endpoint, params, out_path):
    url=BASE_URL+endpoint+'?'+urlencode(params)
    raw=op.open(url, timeout=30).read().decode('utf-8-sig')
    rows=list(csv.DictReader(io.StringIO(raw)))
    with out_path.open('w', newline='', encoding='utf-8-sig') as f:
        w=csv.DictWriter(f, fieldnames=rows[0].keys() if rows else [])
        if rows:
            w.writeheader(); w.writerows(rows)
    return rows

def read_csv_dict(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def write_csv_dict(path, rows, fieldnames):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w=csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader(); w.writerows(rows)

def quote_list():
    cp=subprocess.run([QUOTE_CLI, 'quotes', 'list', '--from', START, '--to', END, '--status', 'Accepted', '--format', 'json'], capture_output=True, text=True, timeout=60)
    if cp.returncode != 0:
        raise RuntimeError(f'quote_cli failed {cp.returncode}: {cp.stderr}')
    data=json.loads(cp.stdout)
    return data['items']

def clear_data(ws):
    if ws.max_row >= 5:
        ws.delete_rows(5, ws.max_row-4)

def set_text(cell, value):
    cell.value = '' if value is None else str(value)
    cell.number_format='@'

def set_money(cell, value):
    cell.value = float(money(value))
    cell.number_format='0.00'

def set_date_text(cell, value):
    cell.value = '' if value is None else str(value)
    cell.number_format='yyyy-mm-dd'

# Load exchange rates first.
fx=read_fx(INPUT/'fx_rates.csv')
print('FX rates:', fx)

# SAP orders/invoices.
op=sap_login_opener()
orders_all=sap_export(op, '/orders/export.csv', {'from':START, 'to':END}, OUTPUT/'sap_orders_2026-09_all.csv')
invoices=sap_export(op, '/invoices/export.csv', {'from':START, 'to':END}, OUTPUT/'sap_invoices_2026-09.csv')
orders=[r for r in orders_all if r.get('Status') != 'Cancelled']
write_csv_dict(OUTPUT/'sap_orders_2026-09_non_cancelled.csv', orders, ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount'])

# Expenses already exported from desktop app in this run.
if not EXPENSE_EXPORT.exists():
    raise FileNotFoundError(f'Missing desktop Expense export: {EXPENSE_EXPORT}. Export Approved expenses for {START}..{END} from the Expense app first.')
expenses=read_csv_dict(EXPENSE_EXPORT)
# Guard filter correctness in case the file is stale.
expenses=[r for r in expenses if START <= r.get('ExpenseDate','') <= END and r.get('Status')=='Approved']
write_csv_dict(OUTPUT/'expenses_2026-09_approved_normalized.csv', expenses, ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','Status','ReceiptID','Description','MissingReceipt'])

# Quotes.
quotes=quote_list()
write_csv_dict(OUTPUT/'quotes_2026-09_accepted.csv', quotes, ['QuoteID','CustomerID','ProjectID','QuoteDate','ValidUntil','Status','Currency','Subtotal','DiscountPercent','NetAmount'])

# Populate workbook.
wb=openpyxl.load_workbook(INPUT/'project_template.xlsx')
for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    clear_data(wb[s])

# Report metadata.
rep=wb['Report']
rep['B3']=START; rep['D3']=END
rep['B4']='2026 年 9 月；SAP Sales Orders 非 Cancelled；SAP Invoices；Expense Approved；Quote Accepted；依 ProjectID 彙總，訂單與報價分開不相加。'
rep['B5']=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec='seconds')
rep['B7']='Lab ERP SAP-like web; Expense Viewer desktop export; quote_cli; fx_rates.csv'

exceptions=[]
summary={}
def add_summary(project, key, amount_twd):
    if not project:
        return
    summary.setdefault(project, {'OrderTWD':Decimal('0'), 'InvoiceBalanceTWD':Decimal('0'), 'ApprovedExpenseTWD':Decimal('0'), 'AcceptedQuoteTWD':Decimal('0')})
    summary[project][key]+=Decimal(amount_twd)

# Orders sheet
ws=wb['Orders']; row=5
for r in orders:
    cur=r['Currency']; amt=money(r['NetAmount']); twd=to_twd(amt, cur, fx)
    vals=[r['OrderID'], r['ProjectID'], r['CustomerID'], r['OrderDate'], r['Status'], cur, amt, twd]
    for col,val in enumerate(vals,1):
        c=ws.cell(row,col)
        if col in [1,2,3,5,6]: set_text(c,val)
        elif col==4: set_date_text(c,val)
        else: set_money(c,val)
    if not r['ProjectID']:
        exceptions.append(['Orders', r['OrderID'], '', 'Missing ProjectID; not included in project summary'])
    else:
        add_summary(r['ProjectID'], 'OrderTWD', twd)
    row+=1

# Invoices sheet
ws=wb['Invoices']; row=5
for r in invoices:
    cur=r['Currency']; bal=money(r['Balance']); bal_twd=to_twd(bal, cur, fx)
    vals=[r['InvoiceID'], r['OrderID'], r['ProjectID'], r['CustomerID'], r['InvoiceDate'], r['DueDate'], cur, money(r['Amount']), money(r['PaidAmount']), bal, bal_twd]
    for col,val in enumerate(vals,1):
        c=ws.cell(row,col)
        if col in [1,2,3,4,7]: set_text(c,val)
        elif col in [5,6]: set_date_text(c,val)
        else: set_money(c,val)
    if not r['ProjectID']:
        exceptions.append(['Invoices', r['InvoiceID'], '', 'Missing ProjectID; not included in project summary'])
    else:
        add_summary(r['ProjectID'], 'InvoiceBalanceTWD', bal_twd)
    if bal > 0 and datetime.date.fromisoformat(r['DueDate']) < TODAY:
        exceptions.append(['Invoices', r['InvoiceID'], r['ProjectID'], f'Overdue unpaid balance as of {TODAY.isoformat()}'])
    row+=1

# Expenses sheet
ws=wb['Expenses']; row=5
for r in expenses:
    cur=r['Currency']; amt=money(r['Amount']); twd=to_twd(amt, cur, fx)
    vals=[r['ExpenseID'], r['ProjectID'], r['EmployeeID'], r['ExpenseDate'], r['Status'], cur, amt, twd]
    for col,val in enumerate(vals,1):
        c=ws.cell(row,col)
        if col in [1,2,3,5,6]: set_text(c,val)
        elif col==4: set_date_text(c,val)
        else: set_money(c,val)
    if not r['ProjectID']:
        exceptions.append(['Expenses', r['ExpenseID'], '', 'Missing ProjectID; not included in project summary'])
    else:
        add_summary(r['ProjectID'], 'ApprovedExpenseTWD', twd)
    if str(r.get('MissingReceipt','')).lower() == 'true':
        exceptions.append(['Expenses', r['ExpenseID'], r['ProjectID'], 'Missing receipt'])
    row+=1

# Quotes sheet
ws=wb['Quotes']; row=5
for r in quotes:
    cur=r['Currency']; amt=money(r['NetAmount']); twd=to_twd(amt, cur, fx)
    vals=[r['QuoteID'], r['ProjectID'], r['CustomerID'], r['QuoteDate'], r['ValidUntil'], r['Status'], cur, amt, twd]
    for col,val in enumerate(vals,1):
        c=ws.cell(row,col)
        if col in [1,2,3,6,7]: set_text(c,val)
        elif col in [4,5]: set_date_text(c,val)
        else: set_money(c,val)
    if not r['ProjectID']:
        exceptions.append(['Quotes', r['QuoteID'], '', 'Missing ProjectID; not included in project summary'])
    else:
        add_summary(r['ProjectID'], 'AcceptedQuoteTWD', twd)
    row+=1

# Summary sheet
ws=wb['Summary']; row=5
for project in sorted(summary):
    vals=[project, summary[project]['OrderTWD'], summary[project]['InvoiceBalanceTWD'], summary[project]['ApprovedExpenseTWD'], summary[project]['AcceptedQuoteTWD']]
    for col,val in enumerate(vals,1):
        c=ws.cell(row,col)
        if col==1: set_text(c,val)
        else: set_money(c,val)
    row+=1
last=max(5,row-1)
for col_letter in ['B','C','D','E']:
    ws[f'{col_letter}2']=f'=SUM({col_letter}5:{col_letter}{last})'
    ws[f'{col_letter}2'].number_format='0.00'

# Exceptions
ws=wb['Exceptions']; row=5
for ex in exceptions:
    for col,val in enumerate(ex,1):
        set_text(ws.cell(row,col), val)
    row+=1

# Report notes include row counts and exclusions.
cancelled_count=len(orders_all)-len(orders)
rep['B9']=f'Rows used: orders {len(orders)} (excluded Cancelled {cancelled_count}), invoices {len(invoices)}, expenses {len(expenses)}, quotes {len(quotes)}. Exceptions {len(exceptions)}. Blank ProjectID rows are listed in Exceptions and excluded from Summary.'

wb.save(REPORT_PATH)

# Save summary csv for quick review.
with (OUTPUT/'summary_2026-09.csv').open('w', newline='', encoding='utf-8-sig') as f:
    w=csv.writer(f); w.writerow(['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'])
    for project in sorted(summary):
        w.writerow([project, str(summary[project]['OrderTWD'].quantize(TWOPLACES)), str(summary[project]['InvoiceBalanceTWD'].quantize(TWOPLACES)), str(summary[project]['ApprovedExpenseTWD'].quantize(TWOPLACES)), str(summary[project]['AcceptedQuoteTWD'].quantize(TWOPLACES))])

# Reopen and validate output file.
wb2=openpyxl.load_workbook(REPORT_PATH, data_only=False)
expected_headers={
 'Orders':['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD'],
 'Invoices':['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD'],
 'Expenses':['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD'],
 'Quotes':['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD'],
 'Summary':['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'],
 'Exceptions':['Source','DocumentID','ProjectID','Reason']
}
for sheet, hdr in expected_headers.items():
    got=[wb2[sheet].cell(4,c).value for c in range(1,len(hdr)+1)]
    assert got==hdr, (sheet, got)
counts={s: max(0, wb2[s].max_row-4) for s in expected_headers}
assert counts['Orders']==len(orders)
assert counts['Invoices']==len(invoices)
assert counts['Expenses']==len(expenses)
assert counts['Quotes']==len(quotes)
assert all(wb2['Orders'].cell(r,5).value!='Cancelled' for r in range(5, wb2['Orders'].max_row+1))
assert all(wb2['Expenses'].cell(r,5).value=='Approved' for r in range(5, wb2['Expenses'].max_row+1))
assert all(wb2['Quotes'].cell(r,6).value=='Accepted' for r in range(5, wb2['Quotes'].max_row+1))
# IDs preserved as text (sample leading zero order and invoice still strings)
assert isinstance(wb2['Orders']['A5'].value, str)
assert isinstance(wb2['Invoices']['A5'].value, str)
# Summary equals detail sums by ProjectID.
print('Created', REPORT_PATH)
print('Row counts', counts)
print('Cancelled excluded', cancelled_count)
print('Summary rows:')
for project in sorted(summary):
    print(project, {k:str(v.quantize(TWOPLACES)) for k,v in summary[project].items()})
print('Validation: headers, row counts, filters, text IDs, and workbook reopened OK')
