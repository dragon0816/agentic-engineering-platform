from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, date
import csv, json, shutil, sys
from openpyxl import load_workbook
from openpyxl.styles import Alignment

BASE = Path('.')
IN = BASE/'input'
OUT = BASE/'output'
DL = OUT/'downloads'
OUT.mkdir(exist_ok=True)

customer_id='C001'
start='2026-09-01'
end='2026-09-30'
as_of=date(2026,10,6)
fetch_time=datetime.now().astimezone().replace(microsecond=0).isoformat()
outfile=OUT/f'project_report_{customer_id}_2026-09.xlsx'

TWOPL = Decimal('0.01')
def D(x):
    if x is None or x=='': return Decimal('0')
    return Decimal(str(x))
def money(x):
    return D(x).quantize(TWOPL, rounding=ROUND_HALF_UP)
def twd(amount, currency, fx):
    return (D(amount)*fx[currency]).quantize(TWOPL, rounding=ROUND_HALF_UP)
def parse_date(s):
    return datetime.strptime(s, '%Y-%m-%d').date() if s else None

# fx rates: csv note contains commas; first two columns are the contract fields
fx={}
with open(IN/'fx_rates.csv', newline='', encoding='utf-8-sig') as f:
    rdr=csv.reader(f)
    header=next(rdr)
    for row in rdr:
        if not row: continue
        fx[row[0]]=D(row[1])
print('FX rates:', fx)

# inputs
orders_path=DL/'orders_C001_2026-09.csv'
invoices_path=DL/'invoices_C001_2026-09.csv'
expenses_path=OUT/'expenses_2026-09_all_projects.csv'
quotes_path=OUT/'quotes_C001_2026-09.json'
for p in [orders_path,invoices_path,expenses_path,quotes_path,IN/'project_template.xlsx']:
    if not p.exists():
        raise FileNotFoundError(p)

def read_csv_dict(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))
orders=read_csv_dict(orders_path)
invoices=read_csv_dict(invoices_path)
all_expenses=read_csv_dict(expenses_path)
quotes=json.loads(quotes_path.read_text(encoding='utf-8'))['items']

project_ids=sorted({r['ProjectID'] for r in orders+invoices+quotes if r.get('ProjectID')})
expenses=[r for r in all_expenses if r.get('ProjectID') in set(project_ids) and start <= r.get('ExpenseDate','') <= end]
print('Project IDs from C001 docs:', project_ids)
print('Row counts before writing:', {'orders':len(orders),'invoices':len(invoices),'expenses_filtered':len(expenses),'quotes':len(quotes)})

# Copy template and load
shutil.copyfile(IN/'project_template.xlsx', outfile)
wb=load_workbook(outfile)

# clear data rows from target sheets, preserving headers and basic layout
for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    ws=wb[s]
    if ws.max_row >= 5:
        ws.delete_rows(5, ws.max_row-4)

# report metadata
ws=wb['Report']
ws['B3']=parse_date(start); ws['B3'].number_format='yyyy-mm-dd'
ws['D3']=parse_date(end); ws['D3'].number_format='yyyy-mm-dd'
ws['B4']=f'CustomerID={customer_id}; period={start} to {end}; currencies converted to TWD using input/fx_rates.csv fixed test rates.'
ws['B5']=fetch_time
ws['B7']='Lab ERP Sales Orders/Invoices; Expense Viewer; quote_cli; fx_rates.csv'
ws['D7']=fetch_time
ws['B9']='Expenses are selected by ProjectID associated with the customer documents in this period. Attention items are listed in Exceptions.'

# helper write sheet
TEXT_COLS={
    'Orders':[1,2,3], 'Invoices':[1,2,3,4], 'Expenses':[1,2,3], 'Quotes':[1,2,3], 'Summary':[1], 'Exceptions':[1,2,3,4]
}
DATE_COLS={'Orders':[4], 'Invoices':[5,6], 'Expenses':[4], 'Quotes':[4,5]}
NUM_FORMAT='0.00'

def write_row(wsname, rownum, vals, money_cols=()):
    ws=wb[wsname]
    for c,v in enumerate(vals,1):
        cell=ws.cell(rownum,c,v)
        if c in TEXT_COLS.get(wsname,[]):
            cell.number_format='@'
            if v is not None: cell.value=str(v)
        if c in DATE_COLS.get(wsname,[]) and v:
            if isinstance(v,str): cell.value=parse_date(v)
            cell.number_format='yyyy-mm-dd'
        if c in money_cols:
            cell.number_format=NUM_FORMAT
            if isinstance(v, Decimal): cell.value=float(v)
            elif v not in (None,''): cell.value=float(D(v))

# details
for i,r in enumerate(orders,5):
    amt=money(r['NetAmount']); atwd=twd(r['NetAmount'],r['Currency'],fx)
    write_row('Orders', i, [r['OrderID'],r['ProjectID'],r['CustomerID'],r['OrderDate'],r['Status'],r['Currency'],amt,atwd], money_cols=[7,8])
for i,r in enumerate(invoices,5):
    bal=money(r['Balance']); btwd=twd(r['Balance'],r['Currency'],fx)
    write_row('Invoices', i, [r['InvoiceID'],r['OrderID'],r['ProjectID'],r['CustomerID'],r['InvoiceDate'],r['DueDate'],r['Currency'],money(r['Amount']),money(r['PaidAmount']),bal,btwd], money_cols=[8,9,10,11])
for i,r in enumerate(expenses,5):
    amt=money(r['Amount']); atwd=twd(r['Amount'],r['Currency'],fx)
    write_row('Expenses', i, [r['ExpenseID'],r['ProjectID'],r['EmployeeID'],r['ExpenseDate'],r['Status'],r['Currency'],amt,atwd], money_cols=[7,8])
for i,r in enumerate(quotes,5):
    amt=money(r['NetAmount']); atwd=twd(r['NetAmount'],r['Currency'],fx)
    write_row('Quotes', i, [r['QuoteID'],r['ProjectID'],r['CustomerID'],r['QuoteDate'],r['ValidUntil'],r['Status'],r['Currency'],amt,atwd], money_cols=[8,9])

# Summary
summary={pid:{'OrderTWD':Decimal('0'), 'InvoiceBalanceTWD':Decimal('0'), 'ApprovedExpenseTWD':Decimal('0'), 'AcceptedQuoteTWD':Decimal('0')} for pid in project_ids}
for r in orders:
    if r['ProjectID']:
        summary.setdefault(r['ProjectID'], {'OrderTWD':Decimal('0'), 'InvoiceBalanceTWD':Decimal('0'), 'ApprovedExpenseTWD':Decimal('0'), 'AcceptedQuoteTWD':Decimal('0')})
        summary[r['ProjectID']]['OrderTWD'] += twd(r['NetAmount'],r['Currency'],fx)
for r in invoices:
    if r['ProjectID']:
        summary.setdefault(r['ProjectID'], {'OrderTWD':Decimal('0'), 'InvoiceBalanceTWD':Decimal('0'), 'ApprovedExpenseTWD':Decimal('0'), 'AcceptedQuoteTWD':Decimal('0')})
        summary[r['ProjectID']]['InvoiceBalanceTWD'] += twd(r['Balance'],r['Currency'],fx)
for r in expenses:
    if r['Status']=='Approved':
        summary.setdefault(r['ProjectID'], {'OrderTWD':Decimal('0'), 'InvoiceBalanceTWD':Decimal('0'), 'ApprovedExpenseTWD':Decimal('0'), 'AcceptedQuoteTWD':Decimal('0')})
        summary[r['ProjectID']]['ApprovedExpenseTWD'] += twd(r['Amount'],r['Currency'],fx)
for r in quotes:
    if r['Status']=='Accepted':
        summary.setdefault(r['ProjectID'], {'OrderTWD':Decimal('0'), 'InvoiceBalanceTWD':Decimal('0'), 'ApprovedExpenseTWD':Decimal('0'), 'AcceptedQuoteTWD':Decimal('0')})
        summary[r['ProjectID']]['AcceptedQuoteTWD'] += twd(r['NetAmount'],r['Currency'],fx)

for i,pid in enumerate(sorted(summary),5):
    s=summary[pid]
    write_row('Summary', i, [pid,s['OrderTWD'],s['InvoiceBalanceTWD'],s['ApprovedExpenseTWD'],s['AcceptedQuoteTWD']], money_cols=[2,3,4,5])
last=max(5,4+len(summary))
ws=wb['Summary']
for col in 'BCDE':
    ws[f'{col}2']=f'=SUM({col}5:{col}{last})'
    ws[f'{col}2'].number_format=NUM_FORMAT

# Exceptions / attention items
exceptions=[]
for r in orders:
    if r['Status']!='Closed':
        exceptions.append(['Orders', r['OrderID'], r['ProjectID'], f"Order status is {r['Status']}"])
for r in invoices:
    bal=D(r['Balance'])
    if bal>0:
        due=parse_date(r['DueDate'])
        if due and due < as_of:
            reason=f"Overdue unpaid balance {r['Currency']} {money(bal)} due {r['DueDate']}"
        else:
            reason=f"Outstanding balance {r['Currency']} {money(bal)} due {r['DueDate']}"
        exceptions.append(['Invoices', r['InvoiceID'], r['ProjectID'], reason])
for r in expenses:
    reasons=[]
    if r['Status']!='Approved': reasons.append(f"Expense status is {r['Status']}")
    if str(r.get('MissingReceipt','')).lower()=='true': reasons.append('Missing receipt')
    if reasons: exceptions.append(['Expenses', r['ExpenseID'], r['ProjectID'], '; '.join(reasons)])
for r in quotes:
    reasons=[]
    valid=parse_date(r['ValidUntil'])
    if r['Status']!='Accepted': reasons.append(f"Quote status is {r['Status']}")
    if valid and valid < as_of: reasons.append(f"ValidUntil {r['ValidUntil']} has passed")
    if reasons: exceptions.append(['Quotes', r['QuoteID'], r['ProjectID'], '; '.join(dict.fromkeys(reasons))])
for i,row in enumerate(exceptions,5):
    write_row('Exceptions', i, row)
    wb['Exceptions'].cell(i,4).alignment=Alignment(wrap_text=True)

# Freeze/filter preservation: set filters around data if absent (safe)
for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    ws=wb[s]
    maxrow=max(ws.max_row,4)
    maxcol=ws.max_column
    ws.auto_filter.ref=f"A4:{ws.cell(4,maxcol).coordinate[0]}{maxrow}" if maxcol <= 26 else ws.auto_filter.ref

wb.save(outfile)
print('Wrote', outfile)

# Verification by reopening saved output
wb2=load_workbook(outfile, data_only=False)
checks=[]
expected_headers={
    'Orders':['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD'],
    'Invoices':['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD'],
    'Expenses':['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD'],
    'Quotes':['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD'],
    'Summary':['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'],
    'Exceptions':['Source','DocumentID','ProjectID','Reason'],
}
for s,h in expected_headers.items():
    got=[wb2[s].cell(4,c).value for c in range(1,len(h)+1)]
    assert got==h, (s, got, h)
row_counts={s: max(0, wb2[s].max_row-4) for s in expected_headers}
assert row_counts['Orders']==len(orders)
assert row_counts['Invoices']==len(invoices)
assert row_counts['Expenses']==len(expenses)
assert row_counts['Quotes']==len(quotes)
assert row_counts['Summary']==len(summary)
assert row_counts['Exceptions']==len(exceptions)
# ID text preserved
assert wb2['Orders']['A5'].value=='0045000109'
assert wb2['Invoices']['A5'].value=='0090000208'
# numeric check examples
assert isinstance(wb2['Orders']['H5'].value, (int,float))
assert round(wb2['Orders']['H7'].value,2)==307125.00  # EUR 8775*35
assert round(wb2['Quotes']['I6'].value,2)==331200.00  # USD 10350*32
# no blank rows within populated area primary IDs
for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    for r in range(5, wb2[s].max_row+1):
        assert wb2[s].cell(r,1).value not in (None,''), f'blank row in {s} {r}'
print('Verified output workbook:')
print(' row_counts=', row_counts)
print(' summary=', {pid:{k: str(v) for k,v in vals.items()} for pid,vals in summary.items()})
print(' exceptions=', len(exceptions))
print(' formulas=', [wb2['Summary'][f'{c}2'].value for c in 'BCDE'])