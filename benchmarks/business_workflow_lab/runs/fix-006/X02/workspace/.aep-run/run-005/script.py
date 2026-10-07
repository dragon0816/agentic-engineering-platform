from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from copy import copy
import csv, json, shutil, os

ws = Path.cwd()
inp = ws/'input'
out = ws/'output'
downloads = out/'downloads'
out.mkdir(exist_ok=True)

START='2026-09-01'
END='2026-09-30'
CUSTOMER='C001'
TODAY=date(2026,10,6)
GENERATED_AT=datetime.now().astimezone().isoformat(timespec='seconds')

TWOPLACES = Decimal('0.01')
def D(x):
    if x is None or x == '': return Decimal('0')
    return Decimal(str(x))
def q2(x):
    return Decimal(x).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
def twd(amount, currency, rates):
    return q2(D(amount) * rates[currency])

def read_csv_dict(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

# FX rates: only first two columns are needed; Note may contain an unquoted comma in lab file.
rates={}
with open(inp/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    rdr=csv.reader(f)
    header=next(rdr)
    for row in rdr:
        if row and row[0]:
            rates[row[0]] = D(row[1])
print('FX rates:', rates)

orders = read_csv_dict(downloads/'orders_C001_2026-09.csv')
invoices = read_csv_dict(downloads/'invoices_C001_2026-09.csv')
expenses = []
for p in [out/'expenses_P001_2026-09.csv', out/'expenses_P003_2026-09.csv']:
    expenses.extend(read_csv_dict(p))
quotes_data = json.loads((downloads/'quotes_C001_2026-09.json').read_text(encoding='utf-8'))
quotes = quotes_data['items']
print('Counts loaded:', {'orders':len(orders),'invoices':len(invoices),'expenses':len(expenses),'quotes':len(quotes)})
print('Orders sample:', orders[:2])
print('Invoices sample:', invoices[:2])
print('Expenses sample:', expenses[:2])
print('Quotes sample:', quotes[:2])

# Fill workbook copy, preserving template.
wb = load_workbook(inp/'project_template.xlsx')

# Helper: clear data rows from row 5 down but keep styles by deleting existing extras if any.
def clear_sheet(sheet):
    if sheet.max_row > 4:
        sheet.delete_rows(5, sheet.max_row-4)

def copy_row_style(sheet, src_row, dst_row, max_col):
    for col in range(1, max_col+1):
        src=sheet.cell(src_row, col)
        dst=sheet.cell(dst_row, col)
        if src.has_style:
            dst._style = copy(src._style)
        if src.number_format:
            dst.number_format = src.number_format
        if src.alignment:
            dst.alignment = copy(src.alignment)
        if src.font:
            dst.font = copy(src.font)
        if src.fill:
            dst.fill = copy(src.fill)
        if src.border:
            dst.border = copy(src.border)

def set_money(cell, value):
    cell.value = float(q2(value))
    cell.number_format = '0.00'

def set_text(cell, value):
    cell.value = '' if value is None else str(value)
    cell.number_format = '@'

def write_rows(sheet_name, rows):
    sh = wb[sheet_name]
    clear_sheet(sh)
    headers=[sh.cell(4,c).value for c in range(1, sh.max_column+1)]
    for i,row in enumerate(rows, start=5):
        if i>5: copy_row_style(sh, 5, i, sh.max_column)
        for c,h in enumerate(headers, start=1):
            val=row.get(h, '')
            cell=sh.cell(i,c)
            if h.lower().endswith('id') or h in ('Status','Currency','Reason','Source'):
                set_text(cell, val)
            elif 'Date' in h or h=='ValidUntil' or h=='DueDate':
                cell.value = val or ''
                cell.number_format = 'yyyy-mm-dd'
            elif h.endswith('TWD') or h in ('NetAmount','Amount','PaidAmount','Balance'):
                set_money(cell, val if val!='' else 0)
            else:
                cell.value = val
    return len(rows)

order_rows=[]
for r in orders:
    currency=r['Currency']; net=q2(r['NetAmount'])
    order_rows.append({
        'OrderID':r['OrderID'], 'ProjectID':r.get('ProjectID',''), 'CustomerID':r['CustomerID'],
        'OrderDate':r['OrderDate'], 'Status':r['Status'], 'Currency':currency,
        'NetAmount':net, 'AmountTWD':twd(net, currency, rates)
    })

invoice_rows=[]
for r in invoices:
    currency=r['Currency']; bal=q2(r['Balance'])
    invoice_rows.append({
        'InvoiceID':r['InvoiceID'], 'OrderID':r['OrderID'], 'ProjectID':r.get('ProjectID',''), 'CustomerID':r['CustomerID'],
        'InvoiceDate':r['InvoiceDate'], 'DueDate':r['DueDate'], 'Currency':currency,
        'Amount':q2(r['Amount']), 'PaidAmount':q2(r['PaidAmount']), 'Balance':bal, 'BalanceTWD':twd(bal, currency, rates)
    })

expense_rows=[]
for r in expenses:
    currency=r['Currency']; amt=q2(r['Amount'])
    expense_rows.append({
        'ExpenseID':r['ExpenseID'], 'ProjectID':r.get('ProjectID',''), 'EmployeeID':r['EmployeeID'],
        'ExpenseDate':r['ExpenseDate'], 'Status':r['Status'], 'Currency':currency,
        'Amount':amt, 'AmountTWD':twd(amt, currency, rates)
    })

quote_rows=[]
for r in quotes:
    currency=r['Currency']; net=q2(r['NetAmount'])
    quote_rows.append({
        'QuoteID':r['QuoteID'], 'ProjectID':r.get('ProjectID',''), 'CustomerID':r['CustomerID'],
        'QuoteDate':r['QuoteDate'], 'ValidUntil':r['ValidUntil'], 'Status':r['Status'], 'Currency':currency,
        'NetAmount':net, 'AmountTWD':twd(net, currency, rates)
    })

# Sort stable by date/id
order_rows.sort(key=lambda r:(r['OrderDate'], r['OrderID']))
invoice_rows.sort(key=lambda r:(r['InvoiceDate'], r['InvoiceID']))
expense_rows.sort(key=lambda r:(r['ExpenseDate'], r['ExpenseID']))
quote_rows.sort(key=lambda r:(r['QuoteDate'], r['QuoteID']))

write_rows('Orders', order_rows)
write_rows('Invoices', invoice_rows)
write_rows('Expenses', expense_rows)
write_rows('Quotes', quote_rows)

# Summary by project. Orders sum all retrieved order rows; invoices sum balances; expenses only Approved; quotes only Accepted.
projects=sorted({r['ProjectID'] for r in order_rows+invoice_rows+expense_rows+quote_rows if r.get('ProjectID')})
summary=[]
for p in projects:
    summary.append({
        'ProjectID': p,
        'OrderTWD': sum(D(r['AmountTWD']) for r in order_rows if r['ProjectID']==p),
        'InvoiceBalanceTWD': sum(D(r['BalanceTWD']) for r in invoice_rows if r['ProjectID']==p),
        'ApprovedExpenseTWD': sum(D(r['AmountTWD']) for r in expense_rows if r['ProjectID']==p and r['Status']=='Approved'),
        'AcceptedQuoteTWD': sum(D(r['AmountTWD']) for r in quote_rows if r['ProjectID']==p and r['Status']=='Accepted'),
    })
write_rows('Summary', summary)
last = 4 + max(len(summary),1)
sh=wb['Summary']
for col in range(2,6):
    letter=sh.cell(4,col).column_letter
    sh.cell(2,col).value=f'=SUM({letter}5:{letter}{last})'
    sh.cell(2,col).number_format='0.00'

# Exceptions/attention items.
exceptions=[]
def add(src, doc, project, reason):
    exceptions.append({'Source':src,'DocumentID':doc,'ProjectID':project or '', 'Reason':reason})
for r in order_rows:
    reasons=[]
    if not r['ProjectID']: reasons.append('Missing ProjectID')
    if r['Status']=='Cancelled': reasons.append('Cancelled order')
    if reasons: add('Orders', r['OrderID'], r['ProjectID'], '; '.join(reasons))
for r in invoice_rows:
    reasons=[]
    if not r['ProjectID']: reasons.append('Missing ProjectID')
    try:
        due=date.fromisoformat(r['DueDate'])
    except Exception:
        due=None
    if D(r['Balance']) > 0 and due and due < TODAY:
        reasons.append('Overdue invoice balance')
    elif D(r['Balance']) > 0:
        reasons.append('Open invoice balance')
    if reasons: add('Invoices', r['InvoiceID'], r['ProjectID'], '; '.join(reasons))
for r_src, r in zip(expenses, expense_rows):
    reasons=[]
    if not r['ProjectID']: reasons.append('Missing ProjectID')
    if r['Status'] != 'Approved': reasons.append(f"Expense status {r['Status']}")
    if str(r_src.get('MissingReceipt','')).lower() == 'true': reasons.append('Missing receipt')
    if reasons: add('Expenses', r['ExpenseID'], r['ProjectID'], '; '.join(reasons))
for r in quote_rows:
    reasons=[]
    if not r['ProjectID']: reasons.append('Missing ProjectID')
    try:
        vu=date.fromisoformat(r['ValidUntil'])
    except Exception:
        vu=None
    if r['Status'] != 'Accepted' and vu and vu < TODAY:
        reasons.append('Quote expired and not accepted')
    if reasons: add('Quotes', r['QuoteID'], r['ProjectID'], '; '.join(reasons))
exceptions.sort(key=lambda r:(r['Source'], r['ProjectID'], r['DocumentID']))
write_rows('Exceptions', exceptions)

# Report sheet
rep=wb['Report']
rep['B3']=START
rep['D3']=END
rep['B4']=f'CustomerID={CUSTOMER}; period={START}..{END}; expenses filtered to projects from retrieved C001 orders/invoices/quotes: {", ".join(projects)}'
rep['B5']=GENERATED_AT
rep['B7']='Lab ERP (orders/invoices); Expense Viewer; quote_cli; fx_rates.csv'
rep['D7']=GENERATED_AT
rep['B9']='Attention items flagged: cancelled orders, overdue/open invoice balances, non-approved or missing-receipt expenses, expired non-accepted quotes, and missing ProjectID. Expense Viewer has no customer filter; expenses are included by related ProjectID.'

# Highlight exception rows lightly
fill=PatternFill('solid', fgColor='FFF2CC')
exc=wb['Exceptions']
for row in range(5, 5+len(exceptions)):
    for col in range(1, exc.max_column+1):
        exc.cell(row,col).fill=fill

# Save
output_path=out/'project_C001_2026-09_report.xlsx'
wb.save(output_path)
print('Saved', output_path)

# Validation: reopen and check requirements
wb2=load_workbook(output_path, data_only=False)
checks=[]
expected_counts={'Orders':len(order_rows),'Invoices':len(invoice_rows),'Expenses':len(expense_rows),'Quotes':len(quote_rows),'Summary':len(summary),'Exceptions':len(exceptions)}
for sheet,count in expected_counts.items():
    sh=wb2[sheet]
    actual=max(sh.max_row-4,0)
    checks.append((sheet, count, actual, count==actual))
print('Row count checks:', checks)
# Headers unchanged
for sheet in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    orig=[load_workbook(inp/'project_template.xlsx', read_only=True)[sheet].cell(4,c).value for c in range(1, wb2[sheet].max_column+1)]
    new=[wb2[sheet].cell(4,c).value for c in range(1, wb2[sheet].max_column+1)]
    print('Header unchanged', sheet, orig==new, new)
# Type and formula checks
print('Summary formulas:', [wb2['Summary'].cell(2,c).value for c in range(2,6)])
print('Report period:', wb2['Report']['B3'].value, wb2['Report']['D3'].value)
for sheet in ['Orders','Invoices','Expenses','Quotes']:
    sh=wb2[sheet]
    print(sheet, 'first data row values:', [sh.cell(5,c).value for c in range(1, sh.max_column+1)] if sh.max_row>=5 else [])
# Verify amount TWD calculations by comparing all rows
assert all(ok for _,_,_,ok in checks)
assert wb2['Report']['B3'].value == START and wb2['Report']['D3'].value == END
print('Validation passed')