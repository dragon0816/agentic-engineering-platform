from pathlib import Path
import csv, json, os, subprocess, sys
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
from collections import defaultdict
from openpyxl import load_workbook

params = json.load(open(os.environ['AEP_WORKFLOW_PARAMS'], encoding='utf-8'))
FROM_DATE = params.get('from_date')
TO_DATE = params.get('to_date')
if not FROM_DATE or not TO_DATE:
    raise SystemExit('from_date and to_date are required')

ROOT = Path.cwd()
IN = ROOT / 'input'
OUT = ROOT / 'output'
DL = OUT / 'downloads'
OUT.mkdir(exist_ok=True)
DL.mkdir(exist_ok=True)

orders_path = DL / 'sap_orders.csv'
invoices_path = DL / 'sap_invoices.csv'
expense_path = OUT / 'expense_approved.csv'
for p in [orders_path, invoices_path, expense_path, IN/'project_template.xlsx', IN/'fx_rates.csv']:
    if not p.exists():
        raise FileNotFoundError(str(p))

D2 = Decimal('0.01')
def money(x):
    if x is None or str(x).strip() == '':
        return Decimal('0')
    return Decimal(str(x).strip()).quantize(D2)

def to_twd(amount, currency, fx):
    cur = (currency or '').strip()
    if cur not in fx:
        raise ValueError(f'Missing FX rate for currency {cur!r}')
    return (money(amount) * fx[cur]).quantize(D2, rounding=ROUND_HALF_UP)

def read_csv(path):
    with path.open(newline='', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

# read FX using first two columns only because Note text may contain commas in the lab file
fx = {}
with (IN/'fx_rates.csv').open(newline='', encoding='utf-8-sig') as f:
    r = csv.reader(f)
    header = next(r)
    for row in r:
        if len(row) >= 2 and row[0].strip():
            fx[row[0].strip()] = Decimal(row[1].strip())
print('FX currencies:', sorted(fx))

orders_raw = read_csv(orders_path)
invoices_raw = read_csv(invoices_path)
expenses_raw = read_csv(expense_path)

# Quote CLI: QuoteDate from/to and Accepted status, JSON decimals parsed as Decimal later.
cli = [sys.executable, r'C:\Users\Chi_L\Documents\ChatGPT\agentic-engineering-platform\benchmarks\business_workflow_lab\quote_cli_mock\run_quote_cli.py', 'quotes', 'list', '--from', FROM_DATE, '--to', TO_DATE, '--status', 'Accepted', '--format', 'json']
res = subprocess.run(cli, capture_output=True, text=True)
if res.returncode != 0:
    raise RuntimeError(f'Quote CLI failed rc={res.returncode}: {res.stderr}')
quote_data = json.loads(res.stdout)
quotes_raw = quote_data.get('items', [])
(OUT/'quotes_accepted.json').write_text(json.dumps(quote_data, ensure_ascii=False, indent=2), encoding='utf-8')

# Filters required by source manuals and user request.
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
    orders_out.append({'OrderID': r['OrderID'], 'ProjectID': r.get('ProjectID',''), 'CustomerID': r.get('CustomerID',''), 'OrderDate': r.get('OrderDate',''), 'Status': r.get('Status',''), 'Currency': r.get('Currency',''), 'NetAmount': money(r.get('NetAmount')), 'AmountTWD': amt_twd})
    if r.get('ProjectID'):
        summary[r['ProjectID']]['OrderTWD'] += amt_twd
    else:
        flag_missing('SAP Orders', r.get('OrderID',''), r.get('ProjectID',''))

invoices_out = []
for r in invoices:
    bal_twd = to_twd(r['Balance'], r['Currency'], fx)
    invoices_out.append({'InvoiceID': r['InvoiceID'], 'OrderID': r.get('OrderID',''), 'ProjectID': r.get('ProjectID',''), 'CustomerID': r.get('CustomerID',''), 'InvoiceDate': r.get('InvoiceDate',''), 'DueDate': r.get('DueDate',''), 'Currency': r.get('Currency',''), 'Amount': money(r.get('Amount')), 'PaidAmount': money(r.get('PaidAmount')), 'Balance': money(r.get('Balance')), 'BalanceTWD': bal_twd})
    if r.get('ProjectID'):
        summary[r['ProjectID']]['InvoiceBalanceTWD'] += bal_twd
    else:
        flag_missing('SAP Invoices', r.get('InvoiceID',''), r.get('ProjectID',''))

expenses_out = []
for r in expenses:
    amt_twd = to_twd(r['Amount'], r['Currency'], fx)
    expenses_out.append({'ExpenseID': r['ExpenseID'], 'ProjectID': r.get('ProjectID',''), 'EmployeeID': r.get('EmployeeID',''), 'ExpenseDate': r.get('ExpenseDate',''), 'Status': r.get('Status',''), 'Currency': r.get('Currency',''), 'Amount': money(r.get('Amount')), 'AmountTWD': amt_twd})
    if r.get('ProjectID'):
        summary[r['ProjectID']]['ApprovedExpenseTWD'] += amt_twd
    else:
        flag_missing('Expense', r.get('ExpenseID',''), r.get('ProjectID',''))

quotes_out = []
for r in quotes:
    amt_twd = to_twd(r['NetAmount'], r['Currency'], fx)
    quotes_out.append({'QuoteID': r['QuoteID'], 'ProjectID': r.get('ProjectID',''), 'CustomerID': r.get('CustomerID',''), 'QuoteDate': r.get('QuoteDate',''), 'ValidUntil': r.get('ValidUntil',''), 'Status': r.get('Status',''), 'Currency': r.get('Currency',''), 'NetAmount': money(r.get('NetAmount')), 'AmountTWD': amt_twd})
    if r.get('ProjectID'):
        summary[r['ProjectID']]['AcceptedQuoteTWD'] += amt_twd
    else:
        flag_missing('Quote CLI', r.get('QuoteID',''), r.get('ProjectID',''))

# Fill a copy of the template, preserving workbook structure.
wb = load_workbook(IN/'project_template.xlsx')

def clear_data(ws, header_row=4):
    if ws.max_row > header_row:
        ws.delete_rows(header_row + 1, ws.max_row - header_row)

def write_rows(sheet, rows, columns):
    ws = wb[sheet]
    clear_data(ws, 4)
    for idx, row in enumerate(rows, start=5):
        for col_idx, col in enumerate(columns, start=1):
            val = row.get(col, '')
            if isinstance(val, Decimal):
                val = float(val)
            ws.cell(idx, col_idx, val)

write_rows('Orders', orders_out, ['OrderID','ProjectID','CustomerID','OrderDate','Status','Currency','NetAmount','AmountTWD'])
write_rows('Invoices', invoices_out, ['InvoiceID','OrderID','ProjectID','CustomerID','InvoiceDate','DueDate','Currency','Amount','PaidAmount','Balance','BalanceTWD'])
write_rows('Expenses', expenses_out, ['ExpenseID','ProjectID','EmployeeID','ExpenseDate','Status','Currency','Amount','AmountTWD'])
write_rows('Quotes', quotes_out, ['QuoteID','ProjectID','CustomerID','QuoteDate','ValidUntil','Status','Currency','NetAmount','AmountTWD'])

summary_rows = []
for pid in sorted(summary):
    vals = summary[pid]
    summary_rows.append({'ProjectID': pid, **{k: vals[k].quantize(D2) for k in ['OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD']}})
write_rows('Summary', summary_rows, ['ProjectID','OrderTWD','InvoiceBalanceTWD','ApprovedExpenseTWD','AcceptedQuoteTWD'])
# Restore total formulas after row insertion/deletion.
sum_ws = wb['Summary']
last = 4 + len(summary_rows)
if len(summary_rows) == 0:
    for c in range(2, 6):
        sum_ws.cell(2, c, 0)
else:
    for c in range(2, 6):
        letter = chr(ord('A') + c - 1)
        sum_ws.cell(2, c, f'=SUM({letter}5:{letter}{last})')

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

# Verification by reopening saved outputs.
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
assert all(wb2['Orders'].cell(r,5).value != 'Cancelled' for r in range(5, 5+len(orders_out)))
assert all(wb2['Expenses'].cell(r,5).value == 'Approved' for r in range(5, 5+len(expenses_out)))
assert all(wb2['Quotes'].cell(r,6).value == 'Accepted' for r in range(5, 5+len(quotes_out)))
# ID columns remain text-like strings, numeric amount cells are numbers.
for sh, idcol in [('Orders',1),('Invoices',1),('Expenses',1),('Quotes',1)]:
    ws = wb2[sh]
    for r in range(5, ws.max_row+1):
        assert isinstance(ws.cell(r,idcol).value, str), f'{sh} ID not text at row {r}'
for sh, amt_cols in [('Orders',[7,8]),('Invoices',[8,9,10,11]),('Expenses',[7,8]),('Quotes',[8,9]),('Summary',[2,3,4,5])]:
    ws = wb2[sh]
    for r in range(5, ws.max_row+1):
        for c in amt_cols:
            assert isinstance(ws.cell(r,c).value, (int,float)), f'{sh} amount not numeric at row {r} col {c}: {ws.cell(r,c).value!r}'

print('Created', out_xlsx)
print('Rows:', {'orders_raw': len(orders_raw), 'orders_non_cancelled': len(orders_out), 'invoices': len(invoices_out), 'expenses_approved': len(expenses_out), 'quotes_accepted': len(quotes_out), 'summary_projects': len(summary_rows), 'exceptions': len(exceptions)})
print('Summary:')
for row in summary_rows:
    print(row)
print('Verified workbook headers, status filters, text IDs, numeric amount cells, summary formulas, and output file reopen.')
