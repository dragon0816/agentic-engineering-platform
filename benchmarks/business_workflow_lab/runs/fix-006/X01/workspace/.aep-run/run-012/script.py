from pathlib import Path
import csv, json, os, subprocess, sys
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from openpyxl import load_workbook

workspace = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\runs\fix-006\X01\workspace')
params = json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8')) if os.environ.get('AEP_WORKFLOW_PARAMS') else {}
FROM_DATE = params.get('from_date', '2026-09-01')
TO_DATE = params.get('to_date', '2026-09-30')
input_dir = workspace / 'input'
output_dir = workspace / 'output'
downloads = output_dir / 'downloads'
output_dir.mkdir(exist_ok=True)
downloads.mkdir(exist_ok=True)
start = datetime.strptime(FROM_DATE, '%Y-%m-%d').date()
end = datetime.strptime(TO_DATE, '%Y-%m-%d').date()

def d(s): return datetime.strptime(str(s)[:10], '%Y-%m-%d').date()
def q2(x): return Decimal(str(x)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
def money(v): return Decimal('0') if v is None or v == '' else Decimal(str(v))
def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as f: return list(csv.DictReader(f))
def write_csv(path, rows, fieldnames):
    with path.open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=fieldnames); w.writeheader()
        for r in rows: w.writerow({k: r.get(k, '') for k in fieldnames})

def quote_items(obj):
    if isinstance(obj, list): return obj
    if isinstance(obj, dict) and isinstance(obj.get('items'), list): return obj['items']
    if isinstance(obj, dict):
        vals=list(obj.values())
        if vals and all(isinstance(v, dict) for v in vals): return vals
    raise SystemExit('Unsupported quote JSON structure')

print('Input files:')
for p in sorted(input_dir.glob('*')): print(' -', p.relative_to(workspace), p.stat().st_size)
print('Extract files before integration:')
for p in sorted(output_dir.rglob('*')):
    if p.is_file(): print(' -', p.relative_to(workspace), p.stat().st_size)

fx = {r['Currency']: money(r['RateToTWD']) for r in read_csv(input_dir / 'fx_rates.csv')}
print('FX currencies:', sorted(fx))
orders_raw = read_csv(downloads / 'sap_orders.csv')
invoices_raw = read_csv(downloads / 'sap_invoices.csv')
expenses_raw = read_csv(output_dir / 'expense_approved.csv')
quote_cli_py = Path(r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py')
cmd = [sys.executable, str(quote_cli_py), 'quotes', 'list', '--from', FROM_DATE, '--to', TO_DATE, '--status', 'Accepted', '--format', 'json']
cp = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', check=True)
quotes_obj = json.loads(cp.stdout)
quotes_raw = quote_items(quotes_obj)

orders = [r for r in orders_raw if start <= d(r['OrderDate']) <= end and r.get('Status') != 'Cancelled']
invoices = [r for r in invoices_raw if start <= d(r['InvoiceDate']) <= end]
expenses = [r for r in expenses_raw if start <= d(r['ExpenseDate']) <= end and r.get('Status') == 'Approved']
quotes = [r for r in quotes_raw if start <= d(r['QuoteDate']) <= end and r.get('Status') == 'Accepted']
print('Filtered rows:', {'orders_non_cancelled': len(orders), 'invoices': len(invoices), 'approved_expenses': len(expenses), 'accepted_quotes': len(quotes)})

order_fields = ['OrderID','CustomerID','CustomerName','ProjectID','OrderDate','Status','Currency','NetAmount']
write_csv(downloads / 'sap_orders.csv', orders, order_fields)
write_csv(downloads / 'sap_orders_sep2026.csv', orders, order_fields)
write_csv(downloads / 'sap_invoices_sep2026.csv', invoices, list(invoices[0].keys()) if invoices else ['InvoiceID','OrderID','CustomerID','ProjectID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance'])
write_csv(output_dir / 'expense_approved_sep2026.csv', expenses, list(expenses[0].keys()) if expenses else ['ExpenseID','EmployeeID','EmployeeName','ProjectID','ExpenseDate','Category','Currency','Amount','Status','ReceiptID','Description','MissingReceipt'])
quotes_obj_out = {'schema_version': 1, 'items': quotes, 'count': len(quotes)}
(output_dir / 'quotes_accepted.json').write_text(json.dumps(quotes_obj_out, ensure_ascii=False, indent=2), encoding='utf-8')
(output_dir / 'quotes_accepted_sep2026.json').write_text(json.dumps(quotes_obj_out, ensure_ascii=False, indent=2), encoding='utf-8')

def amount_twd(currency, amount):
    if currency not in fx: raise SystemExit('Missing FX rate for ' + str(currency))
    return q2(money(amount) * fx[currency])
summary = {}; exceptions = []
def ensure_project(pid):
    if pid not in summary:
        summary[pid] = {'ProjectID': pid, 'OrderTWD': Decimal('0'), 'InvoiceBalanceTWD': Decimal('0'), 'ApprovedExpenseTWD': Decimal('0'), 'AcceptedQuoteTWD': Decimal('0')}
    return summary[pid]

orders_out=[]
for r in orders:
    amt=amount_twd(r['Currency'], r['NetAmount']); pid=str(r.get('ProjectID','') or '')
    out={'OrderID':str(r.get('OrderID','')),'ProjectID':pid,'CustomerID':str(r.get('CustomerID','')),'OrderDate':r.get('OrderDate',''),'Status':r.get('Status',''),'Currency':r.get('Currency',''),'NetAmount':q2(r.get('NetAmount','0')),'AmountTWD':amt}
    orders_out.append(out)
    if pid: ensure_project(pid)['OrderTWD'] += amt
    else: exceptions.append({'Source':'SAP Orders','DocumentID':out['OrderID'],'ProjectID':'','Reason':'Missing ProjectID; excluded from project summary'})
invoices_out=[]
for r in invoices:
    amt=amount_twd(r['Currency'], r['Balance']); pid=str(r.get('ProjectID','') or '')
    out={'InvoiceID':str(r.get('InvoiceID','')),'OrderID':str(r.get('OrderID','')),'ProjectID':pid,'CustomerID':str(r.get('CustomerID','')),'InvoiceDate':r.get('InvoiceDate',''),'DueDate':r.get('DueDate',''),'Currency':r.get('Currency',''),'Amount':q2(r.get('Amount','0')),'PaidAmount':q2(r.get('PaidAmount','0')),'Balance':q2(r.get('Balance','0')),'BalanceTWD':amt}
    invoices_out.append(out)
    if pid: ensure_project(pid)['InvoiceBalanceTWD'] += amt
    else: exceptions.append({'Source':'SAP Invoices','DocumentID':out['InvoiceID'],'ProjectID':'','Reason':'Missing ProjectID; excluded from project summary'})
expenses_out=[]
for r in expenses:
    amt=amount_twd(r['Currency'], r['Amount']); pid=str(r.get('ProjectID','') or '')
    out={'ExpenseID':str(r.get('ExpenseID','')),'ProjectID':pid,'EmployeeID':str(r.get('EmployeeID','')),'ExpenseDate':r.get('ExpenseDate',''),'Status':r.get('Status',''),'Currency':r.get('Currency',''),'Amount':q2(r.get('Amount','0')),'AmountTWD':amt}
    expenses_out.append(out)
    if pid: ensure_project(pid)['ApprovedExpenseTWD'] += amt
    else: exceptions.append({'Source':'Expenses','DocumentID':out['ExpenseID'],'ProjectID':'','Reason':'Missing ProjectID; excluded from project summary'})
quotes_out=[]
for r in quotes:
    amt=amount_twd(r['Currency'], r['NetAmount']); pid=str(r.get('ProjectID','') or '')
    out={'QuoteID':str(r.get('QuoteID','')),'ProjectID':pid,'CustomerID':str(r.get('CustomerID','')),'QuoteDate':r.get('QuoteDate',''),'ValidUntil':r.get('ValidUntil',''),'Status':r.get('Status',''),'Currency':r.get('Currency',''),'NetAmount':q2(r.get('NetAmount','0')),'AmountTWD':amt}
    quotes_out.append(out)
    if pid: ensure_project(pid)['AcceptedQuoteTWD'] += amt
    else: exceptions.append({'Source':'Quotes','DocumentID':out['QuoteID'],'ProjectID':'','Reason':'Missing ProjectID; excluded from project summary'})

summary_rows=[]
for pid in sorted(summary):
    s=summary[pid]
    summary_rows.append({'ProjectID':pid,'OrderTWD':f"{q2(s['OrderTWD']):.2f}",'InvoiceBalanceTWD':f"{q2(s['InvoiceBalanceTWD']):.2f}",'ApprovedExpenseTWD':f"{q2(s['ApprovedExpenseTWD']):.2f}",'AcceptedQuoteTWD':f"{q2(s['AcceptedQuoteTWD']):.2f}"})
write_csv(output_dir / 'project_summary_sep2026.csv', summary_rows, ['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'])

wb = load_workbook(input_dir / 'project_template.xlsx')
def clear_from(sheet, start_row=5):
    sh=wb[sheet]
    if sh.max_row >= start_row: sh.delete_rows(start_row, sh.max_row - start_row + 1)
    return sh
def write_sheet(name, rows, fields):
    sh=clear_from(name, 5)
    if [sh.cell(4,c).value for c in range(1,len(fields)+1)] != fields: raise SystemExit(name + ' template headers differ')
    for i,r in enumerate(rows, start=5):
        for j,f in enumerate(fields, start=1):
            v=r.get(f,'')
            if isinstance(v, Decimal): v=float(v)
            sh.cell(i,j).value=v
rep=wb['Report']; taipei=timezone(timedelta(hours=8)); ts=datetime.now(taipei).isoformat(timespec='seconds')
rep['B3']=FROM_DATE; rep['D3']=TO_DATE
rep['B4']='SAP Sales Orders excluding Cancelled by OrderDate; SAP Invoices by InvoiceDate; Expense Approved by ExpenseDate; Quote CLI Accepted by QuoteDate. Aggregated separately by ProjectID; customer name is not used as a join key; orders and quotes are not combined as revenue.'
rep['B5']=ts; rep['B7']='Lab ERP SAP web; Expense Viewer desktop; quote_cli; fx_rates.csv'; rep['D7']=ts
rep['B9']=f"Rows used: orders {len(orders)} (Cancelled excluded), invoices {len(invoices)}, approved expenses {len(expenses)}, accepted quotes {len(quotes)}. Exceptions list rows missing ProjectID."
write_sheet('Orders', orders_out, ['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD'])
write_sheet('Invoices', invoices_out, ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD'])
write_sheet('Expenses', expenses_out, ['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD'])
write_sheet('Quotes', quotes_out, ['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD'])
sh=clear_from('Summary',5); headers=['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD']
if [sh.cell(4,c).value for c in range(1,6)] != headers: raise SystemExit('Summary template headers differ')
for i,r in enumerate(summary_rows, start=5):
    sh.cell(i,1).value=r['ProjectID']; sh.cell(i,2).value=float(Decimal(r['OrderTWD'])); sh.cell(i,3).value=float(Decimal(r['InvoiceBalanceTWD'])); sh.cell(i,4).value=float(Decimal(r['ApprovedExpenseTWD'])); sh.cell(i,5).value=float(Decimal(r['AcceptedQuoteTWD']))
last=4+len(summary_rows)
for col in 'BCDE': sh[f'{col}2']=f'=SUM({col}5:{col}{last})'
sh=clear_from('Exceptions',5); exc_headers=['Source','DocumentID','ProjectID','Reason']
if [sh.cell(4,c).value for c in range(1,5)] != exc_headers: raise SystemExit('Exceptions template headers differ')
for i,r in enumerate(exceptions, start=5):
    for j,f in enumerate(exc_headers, start=1): sh.cell(i,j).value=r.get(f,'')
out_wb=output_dir / 'project_integration_report.xlsx'; wb.save(out_wb)

# Reopen validation.
assert all(r['Status'] != 'Cancelled' for r in read_csv(downloads/'sap_orders.csv'))
wb2=load_workbook(out_wb, data_only=False)
assert wb2['Report']['B3'].value == FROM_DATE and wb2['Report']['D3'].value == TO_DATE
for row in wb2['Orders'].iter_rows(min_row=5, values_only=True):
    if any(v is not None for v in row): assert row[4] != 'Cancelled'
for row in wb2['Expenses'].iter_rows(min_row=5, values_only=True):
    if any(v is not None for v in row): assert row[4] == 'Approved'
for row in wb2['Quotes'].iter_rows(min_row=5, values_only=True):
    if any(v is not None for v in row): assert row[5] == 'Accepted'
for row in wb2['Summary'].iter_rows(min_row=5, values_only=True):
    if any(v is not None for v in row):
        assert isinstance(row[0], str)
        for val in row[1:5]: assert isinstance(val, (int,float))
print('VALIDATION PASSED')
print('Files written:', [str(p.relative_to(workspace)) for p in [downloads/'sap_orders.csv', downloads/'sap_invoices.csv', output_dir/'expense_approved.csv', output_dir/'quotes_accepted.json', output_dir/'project_summary_sep2026.csv', output_dir/'project_integration_report.xlsx']])