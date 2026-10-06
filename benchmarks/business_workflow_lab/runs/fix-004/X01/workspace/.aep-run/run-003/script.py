import os, json, csv, shutil, subprocess
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from openpyxl import load_workbook

params = json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))
FROM = params['from_date']
TO = params['to_date']
ws = Path.cwd()
out = ws / 'output'
downloads = out / 'downloads'
out.mkdir(exist_ok=True)

TW = timezone(timedelta(hours=8))
generated_at = datetime.now(TW).replace(microsecond=0).isoformat()

def read_csv_rows(path):
    with open(path, newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

def dec(v):
    if v is None or str(v).strip() == '':
        return Decimal('0')
    return Decimal(str(v).strip())

def money(v):
    return dec(v).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# FX rates from attachment; keep only first 2 columns because Note text contains commas in the lab file.
fx = {}
with open(ws/'input'/'fx_rates.csv', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    header = next(reader)
    for row in reader:
        if len(row) >= 2 and row[0].strip():
            fx[row[0].strip()] = dec(row[1])

def twd(amount, currency):
    if currency not in fx:
        raise ValueError(f'Missing FX rate for {currency}')
    return money(dec(amount) * fx[currency])

orders_path = downloads/'sap_orders.csv'
invoices_path = downloads/'sap_invoices.csv'
expenses_path = out/'expense_approved.csv'
for p in [orders_path, invoices_path, expenses_path, ws/'input'/'project_template.xlsx']:
    if not p.exists():
        raise FileNotFoundError(str(p))

raw_orders = read_csv_rows(orders_path)
raw_invoices = read_csv_rows(invoices_path)
raw_expenses = read_csv_rows(expenses_path)

# Quote CLI: public interface only, no direct data file access.
cli = r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py'
cmd = ['python', cli, 'quotes', 'list', '--from', FROM, '--to', TO, '--status', 'Accepted', '--format', 'json']
res = subprocess.run(cmd, cwd=ws, capture_output=True, text=True)
if res.returncode != 0:
    raise RuntimeError(f'quote_cli failed rc={res.returncode}: {res.stderr}')
quote_json = json.loads(res.stdout)
raw_quotes = quote_json.get('items', [])

# Date/status safeguards in case upstream filters change.
def in_range(date_s):
    return FROM <= date_s <= TO

orders = []
exceptions = []
for r in raw_orders:
    if not in_range(r['OrderDate']):
        continue
    if r['Status'] == 'Cancelled':
        exceptions.append({'Source':'Sales Orders','DocumentID':r['OrderID'],'ProjectID':r.get('ProjectID',''),'Reason':'Cancelled order excluded from order total'})
        continue
    if not r.get('ProjectID'):
        exceptions.append({'Source':'Sales Orders','DocumentID':r['OrderID'],'ProjectID':'','Reason':'Missing ProjectID; excluded from project summary'})
    r2 = {k: r.get(k,'') for k in ['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount']}
    r2['AmountTWD'] = twd(r2['NetAmount'], r2['Currency'])
    orders.append(r2)

invoices = []
for r in raw_invoices:
    if not in_range(r['InvoiceDate']):
        continue
    if not r.get('ProjectID'):
        exceptions.append({'Source':'Invoices','DocumentID':r['InvoiceID'],'ProjectID':'','Reason':'Missing ProjectID; excluded from project summary'})
    r2 = {k: r.get(k,'') for k in ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance']}
    r2['BalanceTWD'] = twd(r2['Balance'], r2['Currency'])
    invoices.append(r2)

expenses = []
for r in raw_expenses:
    if not in_range(r['ExpenseDate']) or r['Status'] != 'Approved':
        continue
    if not r.get('ProjectID'):
        exceptions.append({'Source':'Expenses','DocumentID':r['ExpenseID'],'ProjectID':'','Reason':'Missing ProjectID; excluded from project summary'})
    r2 = {k: r.get(k,'') for k in ['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount']}
    r2['AmountTWD'] = twd(r2['Amount'], r2['Currency'])
    expenses.append(r2)

quotes = []
for r in raw_quotes:
    if not in_range(r['QuoteDate']) or r['Status'] != 'Accepted':
        continue
    if not r.get('ProjectID'):
        exceptions.append({'Source':'Quotes','DocumentID':r['QuoteID'],'ProjectID':'','Reason':'Missing ProjectID; excluded from project summary'})
    r2 = {k: r.get(k,'') for k in ['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount']}
    r2['AmountTWD'] = twd(r2['NetAmount'], r2['Currency'])
    quotes.append(r2)

summary = defaultdict(lambda: {'OrderTWD':Decimal('0.00'), 'InvoiceBalanceTWD':Decimal('0.00'), 'ApprovedExpenseTWD':Decimal('0.00'), 'AcceptedQuoteTWD':Decimal('0.00')})
for r in orders:
    if r['ProjectID']:
        summary[r['ProjectID']]['OrderTWD'] += r['AmountTWD']
for r in invoices:
    if r['ProjectID']:
        summary[r['ProjectID']]['InvoiceBalanceTWD'] += r['BalanceTWD']
for r in expenses:
    if r['ProjectID']:
        summary[r['ProjectID']]['ApprovedExpenseTWD'] += r['AmountTWD']
for r in quotes:
    if r['ProjectID']:
        summary[r['ProjectID']]['AcceptedQuoteTWD'] += r['AmountTWD']

# Load template and clear data rows only.
report_path = out / f'project_report_{FROM}_to_{TO}.xlsx'
shutil.copy2(ws/'input'/'project_template.xlsx', report_path)
wb = load_workbook(report_path)

def clear_from(sheet_name, start_row=5):
    sh = wb[sheet_name]
    if sh.max_row >= start_row:
        sh.delete_rows(start_row, sh.max_row - start_row + 1)

for s in ['Orders','Invoices','Expenses','Quotes','Summary','Exceptions']:
    clear_from(s)

def append_dicts(sheet_name, headers, rows):
    sh = wb[sheet_name]
    for r in rows:
        vals=[]
        for h in headers:
            v = r.get(h, '')
            if isinstance(v, Decimal):
                vals.append(float(v))
            else:
                vals.append(v)
        sh.append(vals)

append_dicts('Orders', ['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD'], orders)
append_dicts('Invoices', ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD'], invoices)
append_dicts('Expenses', ['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD'], expenses)
append_dicts('Quotes', ['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD'], quotes)

summary_rows=[]
for pid in sorted(summary):
    d=summary[pid]
    summary_rows.append({'ProjectID':pid, **d})
append_dicts('Summary', ['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'], summary_rows)
append_dicts('Exceptions', ['Source','DocumentID','ProjectID','Reason'], exceptions)

# Fill report metadata.
rep = wb['Report']
rep['B3'] = FROM
rep['D3'] = TO
rep['B4'] = 'SAP Sales Orders: OrderDate in range and Status != Cancelled; SAP Invoices: InvoiceDate in range; Expense Viewer: ExpenseDate in range and Status=Approved; quote_cli: QuoteDate in range and Status=Accepted. Joined and summarized strictly by ProjectID. Orders and quotes are reported separately, not combined as revenue.'
rep['B5'] = generated_at
rep['B7'] = 'Lab ERP SAP web; Expense Viewer desktop; quote_cli; fx_rates.csv'
rep['D7'] = generated_at
# Put counts for traceability in report area.
rep['A9'] = 'Record counts'
rep['B9'] = f'Orders {len(orders)}; Invoices {len(invoices)}; Expenses {len(expenses)}; Quotes {len(quotes)}; Exceptions {len(exceptions)}'

# Fix total formulas on Summary row 2 to cover actual rows.
last = max(5, 4 + len(summary_rows))
for col in ['B','C','D','E']:
    wb['Summary'][f'{col}2'] = f'=SUM({col}5:{col}{last})'

# Keep identifier columns as text.
text_cols = {
    'Orders':['A','B','C'], 'Invoices':['A','B','C','D'], 'Expenses':['A','B','C'],
    'Quotes':['A','B','C'], 'Summary':['A'], 'Exceptions':['A','B','C']
}
for s, cols in text_cols.items():
    sh=wb[s]
    for col in cols:
        for row in range(5, sh.max_row+1):
            sh[f'{col}{row}'].number_format='@'
# Money numeric formatting.
for s in ['Orders','Invoices','Expenses','Quotes','Summary']:
    sh=wb[s]
    for row in range(5, sh.max_row+1):
        for cell in sh[row]:
            if isinstance(cell.value, (int,float)):
                cell.number_format = '#,##0.00'

wb.save(report_path)

# Save run audit JSON and CSV exports for quotes used.
with open(out/'quotes_accepted.json','w',encoding='utf-8') as f:
    json.dump(quote_json, f, ensure_ascii=False, indent=2)
with open(out/'run_audit.json','w',encoding='utf-8') as f:
    json.dump({
        'from_date':FROM, 'to_date':TO, 'generated_at':generated_at, 'fx_rates':{k:str(v) for k,v in fx.items()},
        'source_files': {'orders':str(orders_path), 'invoices':str(invoices_path), 'expenses':str(expenses_path), 'quotes':'quote_cli quotes list'},
        'counts': {'orders_non_cancelled':len(orders), 'invoices':len(invoices), 'approved_expenses':len(expenses), 'accepted_quotes':len(quotes), 'exceptions':len(exceptions), 'summary_projects':len(summary_rows)},
        'rules': ['ProjectID is the only integration key', 'Cancelled orders excluded', 'Orders and quotes summarized in separate columns']
    }, f, ensure_ascii=False, indent=2)

# Verification by reopening saved workbook.
wb2 = load_workbook(report_path, data_only=False)
checks=[]
expected_headers = {
 'Orders':['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD'],
 'Invoices':['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD'],
 'Expenses':['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD'],
 'Quotes':['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD'],
 'Summary':['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'],
 'Exceptions':['Source','DocumentID','ProjectID','Reason']}
for s, hdrs in expected_headers.items():
    actual=[wb2[s].cell(4,c).value for c in range(1,len(hdrs)+1)]
    if actual != hdrs:
        raise AssertionError(f'{s} headers {actual} != {hdrs}')
checks.append('headers match template')
# status/date checks
for row in wb2['Orders'].iter_rows(min_row=5, values_only=True):
    if not row[0]: continue
    if row[4] == 'Cancelled': raise AssertionError('Cancelled order present')
    if not (FROM <= row[3] <= TO): raise AssertionError('order date out of range')
for row in wb2['Expenses'].iter_rows(min_row=5, values_only=True):
    if not row[0]: continue
    if row[4] != 'Approved': raise AssertionError('non-approved expense present')
for row in wb2['Quotes'].iter_rows(min_row=5, values_only=True):
    if not row[0]: continue
    if row[5] != 'Accepted': raise AssertionError('non-accepted quote present')
checks.append('filters verified from saved workbook')
# totals independent recompute from saved sheets by ProjectID
saved_summary={}
for row in wb2['Summary'].iter_rows(min_row=5, values_only=True):
    if row[0]: saved_summary[row[0]] = tuple(money(v or 0) for v in row[1:5])
recalc=defaultdict(lambda:[Decimal('0.00')]*4)
for row in wb2['Orders'].iter_rows(min_row=5, values_only=True):
    if row[0] and row[1]: recalc[row[1]][0] += money(row[7])
for row in wb2['Invoices'].iter_rows(min_row=5, values_only=True):
    if row[0] and row[2]: recalc[row[2]][1] += money(row[10])
for row in wb2['Expenses'].iter_rows(min_row=5, values_only=True):
    if row[0] and row[1]: recalc[row[1]][2] += money(row[7])
for row in wb2['Quotes'].iter_rows(min_row=5, values_only=True):
    if row[0] and row[1]: recalc[row[1]][3] += money(row[8])
recalc={k:tuple(v) for k,v in recalc.items()}
if saved_summary != recalc:
    raise AssertionError(f'summary mismatch saved={saved_summary} recalc={recalc}')
checks.append('summary recomputed by ProjectID matches saved Summary')
print('WROTE', report_path)
print('COUNTS', {'orders_non_cancelled':len(orders), 'invoices':len(invoices), 'approved_expenses':len(expenses), 'accepted_quotes':len(quotes), 'exceptions':len(exceptions), 'summary_projects':len(summary_rows)})
print('CHECKS', '; '.join(checks))
print('SUMMARY')
for row in summary_rows:
    print(row['ProjectID'], *(str(row[k]) for k in ['OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD']))
