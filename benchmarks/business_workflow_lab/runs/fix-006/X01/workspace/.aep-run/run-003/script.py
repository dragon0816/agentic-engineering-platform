from pathlib import Path
import csv, json, os, subprocess, sys
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from collections import defaultdict
from openpyxl import load_workbook

FROM_DATE = '2026-09-01'
TO_DATE = '2026-09-30'
ROOT = Path.cwd()
IN = ROOT / 'input'
OUT = ROOT / 'output'
DL = OUT / 'downloads'
OUT.mkdir(exist_ok=True)
DL.mkdir(exist_ok=True)

orders_path = DL / 'sap_orders_sep2026.csv'
invoices_path = DL / 'sap_invoices_sep2026.csv'
expense_path = OUT / 'expense_approved_sep2026.csv'
print('INPUTS FOR INTEGRATION')
for p in [orders_path, invoices_path, expense_path, IN/'project_template.xlsx', IN/'fx_rates.csv']:
    print('-', p, 'exists=', p.exists(), 'bytes=', p.stat().st_size if p.exists() else None)
    if p.suffix.lower()=='.csv' and p.exists():
        with p.open(newline='', encoding='utf-8-sig') as f:
            rr=csv.reader(f)
            for i,row in zip(range(3), rr): print(' ', i, row)

D2 = Decimal('0.01')
def money(x):
    if x is None or str(x).strip() == '':
        return Decimal('0.00')
    return Decimal(str(x).strip()).quantize(D2)

def to_twd(amount, currency, fx):
    cur = (currency or '').strip()
    if cur not in fx:
        raise ValueError(f'Missing FX rate for currency {cur!r}')
    return (money(amount) * fx[cur]).quantize(D2, rounding=ROUND_HALF_UP)

def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

fx = {}
with (IN/'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    r = csv.reader(f)
    header = next(r)
    for row in r:
        if len(row) >= 2 and row[0].strip():
            fx[row[0].strip()] = Decimal(row[1].strip())
print('FX currencies:', sorted(fx), fx)

orders_raw = read_csv(orders_path)
invoices_raw = read_csv(invoices_path)
expenses_raw = read_csv(expense_path)

cli = [sys.executable, r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py', 'quotes', 'list', '--from', FROM_DATE, '--to', TO_DATE, '--status', 'Accepted', '--format', 'json']
print('Quote CLI:', cli)
res = subprocess.run(cli, capture_output=True, text=True)
print('Quote CLI returncode:', res.returncode)
if res.stderr:
    print('Quote CLI stderr:', res.stderr)
if res.returncode != 0:
    raise RuntimeError(f'Quote CLI failed rc={res.returncode}: {res.stderr}')
quote_data = json.loads(res.stdout)
quotes_raw = quote_data.get('items', [])
(OUT/'quotes_accepted_sep2026.json').write_text(json.dumps(quote_data, ensure_ascii=False, indent=2), encoding='utf-8')

orders = [r for r in orders_raw if r.get('Status') != 'Cancelled']
invoices = list(invoices_raw)
expenses = [r for r in expenses_raw if r.get('Status') == 'Approved']
quotes = [r for r in quotes_raw if r.get('Status') == 'Accepted']

exceptions = []
def flag_missing(source, doc_id, project_id):
    if not (project_id or '').strip():
        exceptions.append({'Source': source, 'DocumentID': doc_id, 'ProjectID': project_id or '', 'Reason': 'Missing ProjectID; excluded from project summary'})

summary = defaultdict(lambda: {'OrderTWD': Decimal('0.00'), 'InvoiceBalanceTWD': Decimal('0.00'), 'ApprovedExpenseTWD': Decimal('0.00'), 'AcceptedQuoteTWD': Decimal('0.00')})

orders_out = []
for r in orders:
    amt_twd = to_twd(r['NetAmount'], r['Currency'], fx)
    row = {'OrderID': str(r['OrderID']), 'ProjectID': r.get('ProjectID',''), 'CustomerID': r.get('CustomerID',''), 'OrderDate': r.get('OrderDate',''), 'Status': r.get('Status',''), 'Currency': r.get('Currency',''), 'NetAmount': money(r.get('NetAmount')), 'AmountTWD': amt_twd}
    orders_out.append(row)
    if row['ProjectID']:
        summary[row['ProjectID']]['OrderTWD'] += amt_twd
    else:
        flag_missing('SAP Orders', row['OrderID'], row['ProjectID'])

invoices_out = []
for r in invoices:
    bal_twd = to_twd(r['Balance'], r['Currency'], fx)
    row = {'InvoiceID': str(r['InvoiceID']), 'OrderID': str(r.get('OrderID','')), 'ProjectID': r.get('ProjectID',''), 'CustomerID': r.get('CustomerID',''), 'InvoiceDate': r.get('InvoiceDate',''), 'DueDate': r.get('DueDate',''), 'Currency': r.get('Currency',''), 'Amount': money(r.get('Amount')), 'PaidAmount': money(r.get('PaidAmount')), 'Balance': money(r.get('Balance')), 'BalanceTWD': bal_twd}
    invoices_out.append(row)
    if row['ProjectID']:
        summary[row['ProjectID']]['InvoiceBalanceTWD'] += bal_twd
    else:
        flag_missing('SAP Invoices', row['InvoiceID'], row['ProjectID'])

expenses_out = []
for r in expenses:
    amt_twd = to_twd(r['Amount'], r['Currency'], fx)
    row = {'ExpenseID': str(r['ExpenseID']), 'ProjectID': r.get('ProjectID',''), 'EmployeeID': r.get('EmployeeID',''), 'ExpenseDate': r.get('ExpenseDate',''), 'Status': r.get('Status',''), 'Currency': r.get('Currency',''), 'Amount': money(r.get('Amount')), 'AmountTWD': amt_twd}
    expenses_out.append(row)
    if row['ProjectID']:
        summary[row['ProjectID']]['ApprovedExpenseTWD'] += amt_twd
    else:
        flag_missing('Expense', row['ExpenseID'], row['ProjectID'])

quotes_out = []
for r in quotes:
    amt_twd = to_twd(r['NetAmount'], r['Currency'], fx)
    row = {'QuoteID': str(r['QuoteID']), 'ProjectID': r.get('ProjectID',''), 'CustomerID': r.get('CustomerID',''), 'QuoteDate': r.get('QuoteDate',''), 'ValidUntil': r.get('ValidUntil',''), 'Status': r.get('Status',''), 'Currency': r.get('Currency',''), 'NetAmount': money(r.get('NetAmount')), 'AmountTWD': amt_twd}
    quotes_out.append(row)
    if row['ProjectID']:
        summary[row['ProjectID']]['AcceptedQuoteTWD'] += amt_twd
    else:
        flag_missing('Quote CLI', row['QuoteID'], row['ProjectID'])

wb = load_workbook(IN/'project_template.xlsx')

def clear_data(ws, header_row=4):
    if ws.max_row > header_row:
        ws.delete_rows(header_row + 1, ws.max_row - header_row)

def excel_value(v):
    if isinstance(v, Decimal):
        return float(v)
    return v

def write_rows(sheet, rows, columns):
    ws = wb[sheet]
    clear_data(ws, 4)
    for idx, row in enumerate(rows, start=5):
        for col_idx, col in enumerate(columns, start=1):
            ws.cell(idx, col_idx, excel_value(row.get(col, '')))

write_rows('Orders', orders_out, ['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD'])
write_rows('Invoices', invoices_out, ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD'])
write_rows('Expenses', expenses_out, ['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD'])
write_rows('Quotes', quotes_out, ['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD'])

summary_rows = []
for pid in sorted(summary):
    vals = summary[pid]
    summary_rows.append({'ProjectID': pid, **{k: vals[k].quantize(D2) for k in ['OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD']}})
write_rows('Summary', summary_rows, ['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'])
sum_ws = wb['Summary']
last = 4 + len(summary_rows)
for c in range(2, 6):
    letter = chr(ord('A') + c - 1)
    sum_ws.cell(2, c, f'=SUM({letter}5:{letter}{last})' if summary_rows else 0)

write_rows('Exceptions', exceptions, ['Source','DocumentID','ProjectID','Reason'])

rep = wb['Report']
rep['B3'] = FROM_DATE
rep['D3'] = TO_DATE
rep['B4'] = 'SAP Sales Orders excluding Cancelled by OrderDate; SAP Invoices by InvoiceDate; Expense Approved by ExpenseDate; Quote CLI Accepted by QuoteDate. Aggregated separately by ProjectID; customer name is not used as a join key; orders and quotes are not combined as revenue.'
now = datetime.now().astimezone().isoformat(timespec='seconds')
rep['B5'] = now
rep['B7'] = 'Lab ERP SAP web; Expense Viewer desktop; quote_cli; fx_rates.csv'
rep['D7'] = now

out_xlsx = OUT / 'project_integration_report.xlsx'
wb.save(out_xlsx)

# Write simple reconciliation CSV for visibility.
with (OUT/'project_summary_sep2026.csv').open('w', newline='', encoding='utf-8-sig') as f:
    cols=['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD']
    w=csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for row in summary_rows:
        w.writerow({k: str(row[k]) for k in cols})

# Verification by reopening outputs.
wb2 = load_workbook(out_xlsx, data_only=False)
expected_headers = {
    'Orders': ['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD'],
    'Invoices': ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD'],
    'Expenses': ['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD'],
    'Quotes': ['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD'],
    'Summary': ['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'],
    'Exceptions': ['Source','DocumentID','ProjectID','Reason'],
}
for sh, hdr in expected_headers.items():
    got = [wb2[sh].cell(4, i).value for i in range(1, len(hdr)+1)]
    assert got == hdr, f'{sh} headers mismatch: {got}'
assert wb2['Report']['B3'].value == FROM_DATE and wb2['Report']['D3'].value == TO_DATE
assert all(wb2['Orders'].cell(r,5).value != 'Cancelled' for r in range(5, 5+len(orders_out)))
assert all(wb2['Expenses'].cell(r,5).value == 'Approved' for r in range(5, 5+len(expenses_out)))
assert all(wb2['Quotes'].cell(r,6).value == 'Accepted' for r in range(5, 5+len(quotes_out)))
for sh, idcol in [('Orders',1),('Invoices',1),('Expenses',1),('Quotes',1)]:
    ws2 = wb2[sh]
    for r in range(5, ws2.max_row+1):
        assert isinstance(ws2.cell(r,idcol).value, str), f'{sh} ID not text at row {r}'
for sh, amt_cols in [('Orders',[7,8]),('Invoices',[8,9,10,11]),('Expenses',[7,8]),('Quotes',[8,9]),('Summary',[2,3,4,5])]:
    ws2 = wb2[sh]
    for r in range(5, ws2.max_row+1):
        for c in amt_cols:
            assert isinstance(ws2.cell(r,c).value, (int,float)), f'{sh} amount not numeric at row {r} col {c}: {ws2.cell(r,c).value!r}'
# Check row counts exactly match written rows.
for sh, count in [('Orders',len(orders_out)),('Invoices',len(invoices_out)),('Expenses',len(expenses_out)),('Quotes',len(quotes_out)),('Summary',len(summary_rows)),('Exceptions',len(exceptions))]:
    actual = max(wb2[sh].max_row - 4, 0)
    assert actual == count, f'{sh} row count {actual} != {count}'

print('Created', out_xlsx)
print('Created', OUT/'project_summary_sep2026.csv')
print('Created', OUT/'quotes_accepted_sep2026.json')
print('Rows:', {'orders_raw': len(orders_raw), 'orders_non_cancelled': len(orders_out), 'invoices': len(invoices_out), 'expenses_approved': len(expenses_out), 'quotes_accepted': len(quotes_out), 'summary_projects': len(summary_rows), 'exceptions': len(exceptions)})
print('Summary rows:')
for row in summary_rows:
    print(row)
print('Verification passed: reopened workbook, checked template headers, date cells, row counts, non-Cancelled orders, Approved expenses, Accepted quotes, text IDs, numeric amounts, and summary formulas.')
